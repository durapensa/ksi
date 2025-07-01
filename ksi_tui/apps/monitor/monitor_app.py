"""
KSI Monitor - Real-time system monitoring dashboard.

Features:
- Live system health indicators
- Active agent tracking
- Real-time event stream
- Performance metrics
- Multi-pane dashboard layout
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Static, Label, Tree, DataTable, Button
from textual.reactive import reactive
from textual import events, work
from textual.timer import Timer

# Import our components and services
from ksi_tui.components import (
    EventStreamWidget,
    MetricsBar,
    ConnectionStatus,
    Metric,
    EventSeverity,
)
from ksi_tui.services import (
    MonitorService,
    SystemHealth,
    AgentInfo,
    EventInfo,
    PerformanceMetrics,
)
from ksi_tui.themes import theme_manager
from ksi_tui.utils import (
    format_timestamp,
    format_duration,
    format_bytes,
    format_number,
)
from ksi_common.config import config


class HealthPanel(Container):
    """System health status panel."""
    
    def compose(self) -> ComposeResult:
        """Compose the health panel."""
        with Vertical(classes="panel health-panel"):
            yield Label("System Health", classes="panel-header")
            yield Static("Checking...", id="health-status", classes="health-status")
            yield Static("", id="health-details", classes="health-details")
    
    def update_health(self, health: SystemHealth) -> None:
        """Update health display."""
        status_widget = self.query_one("#health-status", Static)
        details_widget = self.query_one("#health-details", Static)
        
        # Status line with icon
        if health.is_healthy:
            status_icon = "🟢"
            status_text = "Healthy"
            status_class = "status-healthy"
        elif health.status == "degraded":
            status_icon = "🟡"
            status_text = "Degraded"
            status_class = "status-degraded"
        else:
            status_icon = "🔴"
            status_text = "Error"
            status_class = "status-error"
        
        status_widget.update(f"{status_icon} Status: {status_text}")
        status_widget.set_classes(f"health-status {status_class}")
        
        # Details
        details_lines = []
        details_lines.append(f"Agents: {health.active_agents}")
        details_lines.append(f"Conversations: {health.active_conversations}")
        
        if health.memory_usage:
            details_lines.append(f"Memory: {health.memory_usage}")
        
        if health.uptime:
            details_lines.append(f"Uptime: {health.uptime}")
        
        if health.errors:
            details_lines.append("")
            details_lines.append("[red]Errors:[/]")
            for error in health.errors[:3]:  # Show first 3 errors
                details_lines.append(f"  • {error}")
        
        details_widget.update("\n".join(details_lines))


class AgentTreePanel(Container):
    """Active agents tree view panel."""
    
    def compose(self) -> ComposeResult:
        """Compose the agent tree panel."""
        with Vertical(classes="panel agent-panel"):
            yield Label("Active Agents", classes="panel-header")
            yield Tree("Agents", id="agent-tree", classes="agent-tree")
    
    def update_agents(self, agents: List[AgentInfo]) -> None:
        """Update the agent tree."""
        tree = self.query_one("#agent-tree", Tree)
        tree.clear()
        
        # Group agents by status
        active_agents = []
        idle_agents = []
        terminated_agents = []
        
        for agent in agents:
            if agent.status == "active":
                active_agents.append(agent)
            elif agent.status == "idle":
                idle_agents.append(agent)
            else:
                terminated_agents.append(agent)
        
        # Add active agents
        if active_agents:
            active_node = tree.root.add("🟢 Active", expand=True)
            for agent in active_agents:
                self._add_agent_node(active_node, agent)
        
        # Add idle agents
        if idle_agents:
            idle_node = tree.root.add("🟡 Idle", expand=True)
            for agent in idle_agents:
                self._add_agent_node(idle_node, agent)
        
        # Add terminated agents (last 5)
        if terminated_agents:
            term_node = tree.root.add("⚫ Terminated", expand=False)
            for agent in terminated_agents[-5:]:
                self._add_agent_node(term_node, agent)
    
    def _add_agent_node(self, parent_node, agent: AgentInfo) -> None:
        """Add an agent node to the tree."""
        # Agent main node
        agent_label = f"{agent.agent_id} [{agent.profile}]"
        agent_node = parent_node.add(agent_label)
        
        # Add details
        if agent.spawned_at:
            spawn_time = format_timestamp(agent.spawned_at, relative=True)
            agent_node.add_leaf(f"Started: {spawn_time}")
        
        if agent.parent_id:
            agent_node.add_leaf(f"Parent: {agent.parent_id}")
        
        if agent.children:
            children_node = agent_node.add(f"Children ({len(agent.children)})")
            for child_id in agent.children[:5]:  # Show first 5
                children_node.add_leaf(child_id)
        
        if agent.permissions:
            agent_node.add_leaf(f"Permissions: {agent.permissions}")


class MetricsPanel(Container):
    """Performance metrics panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._metrics_history: List[PerformanceMetrics] = []
    
    def compose(self) -> ComposeResult:
        """Compose the metrics panel."""
        with Vertical(classes="panel metrics-panel"):
            yield Label("Performance Metrics", classes="panel-header")
            
            # Use our MetricsBar component
            yield MetricsBar(
                metrics=[
                    Metric("Events/s", 0, "evt/s", "rate", 100, "green", "📊"),
                    Metric("Queue", 0, "items", "count", 50, "yellow", "📥"),
                    Metric("Latency", 0, "ms", "count", 1000, "blue", "⏱️"),
                    Metric("Connections", 0, "conn", "count", 100, "cyan", "🔌"),
                ],
                layout="vertical",
                show_sparklines=True,
                id="metrics-bar"
            )
    
    def update_metrics(self, metrics: Optional[PerformanceMetrics]) -> None:
        """Update metrics display."""
        if not metrics:
            return
        
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 60:  # Keep last minute
            self._metrics_history.pop(0)
        
        # Update metrics bar
        metrics_bar = self.query_one("#metrics-bar", MetricsBar)
        metrics_bar.update_metrics({
            "Events/s": metrics.events_per_second,
            "Queue": float(metrics.completion_queue_size),
            "Latency": metrics.average_latency_ms or 0,
            "Connections": float(metrics.active_connections),
        })


class MonitorApp(App):
    """The main monitoring dashboard application."""
    
    @property
    def CSS(self) -> str:
        """Get CSS with theme colors applied."""
        return theme_manager.css + f"""
    /* App-specific styles */
    MonitorApp {{
        background: {theme_manager.get_color('base')};
    }}
    
    /* Dashboard grid layout */
    #dashboard {{
        layout: grid;
        grid-size: 3 2;
        grid-columns: 1fr 3fr 1fr;
        grid-rows: 1fr 3fr;
        height: 100%;
        padding: 1;
        gap: 1;
    }}
    
    /* Panels */
    .panel {{
        background: {theme_manager.get_color('mantle')};
        border: round {theme_manager.get_color('surface1')};
        padding: 1;
        overflow: auto;
    }}
    
    .panel-header {{
        background: {theme_manager.get_color('surface0')};
        color: {theme_manager.get_color('lavender')};
        text-style: bold;
        padding: 0 1;
        height: 1;
        margin-bottom: 1;
    }}
    
    /* Health panel */
    .health-panel {{
        grid-column-span: 1;
    }}
    
    .health-status {{
        text-style: bold;
        margin-bottom: 1;
    }}
    
    .status-healthy {{
        color: {theme_manager.get_color('green')};
    }}
    
    .status-degraded {{
        color: {theme_manager.get_color('yellow')};
    }}
    
    .status-error {{
        color: {theme_manager.get_color('red')};
    }}
    
    .health-details {{
        color: {theme_manager.get_color('subtext0')};
    }}
    
    /* Control panel */
    .control-panel {{
        grid-column-span: 1;
        layout: vertical;
    }}
    
    .control-panel Button {{
        width: 100%;
        margin-bottom: 1;
    }}
    
    /* Agent panel */
    .agent-panel {{
        grid-row-span: 2;
    }}
    
    .agent-tree {{
        height: 100%;
    }}
    
    /* Event stream panel */
    .event-panel {{
        grid-column-span: 1;
        grid-row-span: 2;
    }}
    
    /* Metrics panel */
    .metrics-panel {{
        grid-column-span: 1;
        grid-row-span: 2;
    }}
    
    /* Connection status */
    #connection-container {{
        dock: bottom;
        height: 1;
        background: {theme_manager.get_color('surface0')};
        border-top: tall {theme_manager.get_color('surface1')};
        padding: 0 1;
        align: left middle;
    }}
    """
    
    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+c", "clear_events", "Clear Events"),
        Binding("ctrl+p", "pause", "Pause/Resume"),
        Binding("ctrl+f", "filter", "Filter Events"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
    ]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        update_interval: Optional[float] = None,
    ):
        """Initialize the monitor app."""
        super().__init__()
        self.client_id = client_id or config.tui_monitor_client_id
        self.update_interval = update_interval or config.tui_monitor_update_interval
        
        # Services
        self.monitor_service = MonitorService(client_id=self.client_id)
        
        # State
        self.paused = False
        self._update_timer: Optional[Timer] = None
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        # Main dashboard grid
        with Grid(id="dashboard"):
            # Top row: Health, Controls, Metrics header
            yield HealthPanel(classes="health-panel")
            
            with Vertical(classes="panel control-panel"):
                yield Label("Controls", classes="panel-header")
                yield Button("Refresh", id="refresh-btn", variant="primary")
                yield Button("Clear Events", id="clear-btn", variant="warning")
                yield Button("Pause", id="pause-btn")
                yield Button("Export Events", id="export-btn")
            
            # Bottom row: Agents, Events, Metrics
            yield AgentTreePanel(classes="agent-panel")
            
            # Event stream takes center position
            with Container(classes="panel event-panel"):
                yield Label("Event Stream", classes="panel-header")
                yield EventStreamWidget(
                    max_events=1000,
                    auto_scroll=True,
                    show_filter=True,
                    id="event-stream"
                )
            
            yield MetricsPanel(classes="metrics-panel")
        
        # Connection status
        with Container(id="connection-container"):
            yield ConnectionStatus(id="connection-status", compact=False)
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize when app starts."""
        # Set window title
        self.title = "KSI Monitor"
        self.sub_title = "System Dashboard"
        
        # Connect to daemon
        await self._connect_to_daemon()
        
        # Start update timer
        self._update_timer = self.set_interval(
            self.update_interval,
            self._update_dashboard
        )
    
    @work(exclusive=True)
    async def _connect_to_daemon(self) -> None:
        """Connect to the KSI daemon."""
        status = self.query_one("#connection-status", ConnectionStatus)
        status.set_connecting()
        
        try:
            await self.monitor_service.connect()
            status.set_connected()
            
            # Set up event handler
            def handle_event(event: EventInfo):
                # Display in event stream
                if not self.paused:
                    self.call_from_thread(self._display_event, event)
            
            # Subscribe to all events
            await self.monitor_service.subscribe_events(["*"], handle_event)
            
            # Initial update
            await self._update_dashboard()
            
        except Exception as e:
            status.set_error(str(e))
            self.notify(f"Failed to connect: {e}", severity="error")
    
    def _display_event(self, event: EventInfo) -> None:
        """Display an event in the stream."""
        event_stream = self.query_one("#event-stream", EventStreamWidget)
        
        # Map event names to severity
        severity = EventSeverity.INFO
        if "error" in event.event_name.lower():
            severity = EventSeverity.ERROR
        elif "warning" in event.event_name.lower():
            severity = EventSeverity.WARNING
        elif event.event_name.startswith("system:"):
            severity = EventSeverity.DEBUG
        
        event_stream.add_event(
            event_name=event.event_name,
            data=event.data,
            severity=severity,
            client_id=event.client_id,
            correlation_id=event.correlation_id,
            timestamp=event.timestamp,
        )
    
    async def _update_dashboard(self) -> None:
        """Update all dashboard components."""
        if self.paused or not self.monitor_service.connected:
            return
        
        try:
            # Get latest data
            health = await self.monitor_service.get_health()
            agents = await self.monitor_service.get_agents()
            metrics = self.monitor_service.get_latest_metrics()
            
            # Update UI components
            self.query_one(HealthPanel).update_health(health)
            self.query_one(AgentTreePanel).update_agents(agents)
            self.query_one(MetricsPanel).update_metrics(metrics)
            
            # Update connection latency
            if metrics and metrics.average_latency_ms:
                status = self.query_one("#connection-status", ConnectionStatus)
                status.update_latency(metrics.average_latency_ms)
            
        except Exception as e:
            self.notify(f"Update error: {e}", severity="warning")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "clear-btn":
            self.action_clear_events()
        elif event.button.id == "pause-btn":
            self.action_pause()
        elif event.button.id == "export-btn":
            self.action_export_events()
    
    def action_refresh(self) -> None:
        """Refresh all data."""
        asyncio.create_task(self._update_dashboard())
        self.notify("Dashboard refreshed")
    
    def action_clear_events(self) -> None:
        """Clear the event stream."""
        event_stream = self.query_one("#event-stream", EventStreamWidget)
        event_stream.clear_events()
        self.notify("Events cleared")
    
    def action_pause(self) -> None:
        """Toggle pause state."""
        self.paused = not self.paused
        pause_btn = self.query_one("#pause-btn", Button)
        
        if self.paused:
            pause_btn.label = "Resume"
            pause_btn.variant = "success"
            self.notify("Monitoring paused")
        else:
            pause_btn.label = "Pause"
            pause_btn.variant = "default"
            self.notify("Monitoring resumed")
    
    def action_filter(self) -> None:
        """Focus the event filter input."""
        # Focus the filter input in the event stream
        event_stream = self.query_one("#event-stream", EventStreamWidget)
        filter_input = event_stream.query_one("#event-filter")
        filter_input.focus()
    
    def action_export_events(self) -> None:
        """Export events to file."""
        # TODO: Implement event export
        self.notify("Event export coming soon!")
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """**Keyboard Shortcuts:**
• Ctrl+R - Refresh dashboard
• Ctrl+C - Clear event stream
• Ctrl+P - Pause/Resume monitoring
• Ctrl+F - Focus event filter
• Ctrl+Q - Quit
• F1 - This help

**Event Filters:**
Use patterns like:
• agent:* - All agent events
• completion:* - All completion events
• error - Events with "error" in name
• agent:spawn,agent:terminate - Multiple patterns"""
        
        self.notify(help_text, title="Monitor Help", timeout=10)
    
    def action_quit(self) -> None:
        """Quit the application."""
        asyncio.create_task(self._cleanup_and_exit())
    
    async def _cleanup_and_exit(self) -> None:
        """Clean up and exit."""
        if self._update_timer:
            self._update_timer.stop()
        
        try:
            await self.monitor_service.disconnect()
        except Exception:
            pass
        
        self.exit()


def main():
    """Run the monitor application."""
    app = MonitorApp()
    app.run()


if __name__ == "__main__":
    main()
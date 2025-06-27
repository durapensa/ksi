# KSI Monitor Textual: Comprehensive Design & Implementation Plan

## Executive Summary

This document outlines the design and implementation strategy for `monitor_textual.py`, a ground-up rewrite of KSI's monitoring interface using modern Textual best practices. The new monitor will provide comprehensive, real-time visibility into all KSI daemon operations with an event-first architecture designed around the pull-based event log system.

## Current State Analysis

### Problems with Existing `monitor_tui.py`
- **Architectural Debt**: Retrofitted onto push-based design, event log polling is a band-aid
- **Limited Coverage**: Only handles 2 of 6+ event namespaces  
- **Performance Issues**: Polls every 0.5s but shows only incremental updates
- **State Complexity**: Multiple boolean flags (`connected`, `paused`, `debug_mode`) scattered throughout
- **Poor UX**: Events scattered across multiple logs without clear organization
- **Mixed Concerns**: Debugging features intertwined with monitoring UI
- **Technical Debt**: 673 lines, 42 classes/methods with complex interdependencies

### KSI Daemon Monitoring Capabilities

**6 Complete Event Namespaces:**
```
system:*      - health, shutdown, discover, help
completion:*  - request, async (with rich metadata)
agent:*       - spawn, terminate, list, send_message  
state:*       - get, set, delete (persistent storage)
message:*     - subscribe, publish, unsubscribe (pub/sub)
conversation:* - list, search, get, export, stats
```

**Rich Event Data Available:**
- Timestamps with microsecond precision
- Client correlation and request tracing
- Performance metrics (duration, API time, queue time)
- Cost tracking (tokens, pricing)
- Session continuity tracking
- Error classification and handling

## Design Philosophy

### Core Principles
1. **Event-First Architecture**: Built around event log API from the ground up
2. **Comprehensive Coverage**: Monitor ALL daemon capabilities, not just completions
3. **Real-time + Historical**: Live updates with deep historical analysis
4. **Performance Focused**: Efficient updates, smart caching, minimal overhead
5. **Beautiful & Functional**: Modern aesthetics that enhance usability
6. **Extensible Design**: Easy to add new monitoring capabilities

### Modern Textual Best Practices
- **Reactive Data Flow**: Events → Model → View updates
- **Clean MVC Separation**: Model (data), View (UI), Controller (logic)
- **CSS-First Styling**: Leverage Textual's CSS for modern aesthetics
- **Responsive Layout**: Adapt gracefully to different terminal sizes
- **Keyboard Navigation**: Full accessibility and power-user efficiency
- **Widget Composition**: Reusable components with clear interfaces

## UI Design Options

### Option A: Executive Dashboard 🎛️

**Concept**: High-level overview optimized for system administrators and operations teams.

```
┌─ KSI System Monitor ─────────────────────────────────────────────────────┐
│ ● Live      🔄 1.2k events    ⏱️  2.3s avg    💰 $0.45    👥 5 active    │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─Completions──┐ ┌─Agents──────┐ ┌─System──────┐ ┌─Messages────┐      │
│ │  📊 24 req   │ │ 🤖 agent_1  │ │ 💚 Healthy  │ │ 📨 15 pub   │      │
│ │  ⚡ 1.2s avg │ │ 🤖 agent_2  │ │ 💾 98% disk │ │ 🔔 8 sub    │      │  
│ │  🎯 98% ok   │ │ 🤖 research │ │ 🧠 12MB mem │ │ 📡 3 active │      │
│ └──────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │
├─Event Stream─────────────────────────────────────────────────────────────┤
│ 15:30:45 completion:request  event_client_abc  "What is 2+2?"      1.2s │
│ 15:30:46 agent:spawn        admin_xyz         profile=researcher   ok   │
│ 15:30:47 transport:connect  monitor_123       capabilities=monitor      │
│ 15:30:48 state:set          agent_abc         key=status val=active     │
└─[F]ilter [S]earch [E]xport [H]istory [D]etails ─ Q:quit ─────────────────┘
```

**Strengths:**
- Immediate system health overview
- Perfect for NOC/operations center displays
- Aggregated metrics and trends
- Quick problem identification

**Use Cases:**
- System administrators monitoring health
- Operations teams tracking SLA metrics
- Management dashboards
- Alert correlation

**Technical Implementation:**
```python
class DashboardView(Container):
    def compose(self) -> ComposeResult:
        with Container(id="status-bar"):
            yield StatusIndicators()
        with Horizontal(id="metrics-grid"):
            yield CompletionMetrics()
            yield AgentMetrics() 
            yield SystemMetrics()
            yield MessageMetrics()
        with Container(id="event-stream"):
            yield LiveEventStream()
```

### Option B: Timeline Explorer 📅

**Concept**: Chronological exploration of events with advanced filtering and time navigation.

```
┌─ Event Timeline ─────────────────────── [◀ ─5m─ ▶] ─────────────────────┐
│ ┌─Filters────────────────────────────────────────────────────────────┐ │
│ │ ✓completion ✓agent ✓system ✓transport │ Client: [all▼] Time: [1h▼] │ │
│ └────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│ 15:30:45.123 │ completion:request ● event_client_abc                    │
│              │ ┌─Request Details─────────────────────────────────────┐  │
│              │ │ Prompt: "What is 2+2? Please explain step by step" │  │
│              │ │ Model: claude-3-5-sonnet ⏱️ 1.234s 💰 $0.003     │  │
│              │ │ Session: fd5cacf7-ec8b... (continuing)              │  │
│              │ └─────────────────────────────────────────────────────┘  │
│ 15:30:46.234 │ agent:spawn ● admin_xyz                                  │
│              │ Profile: researcher  Config: {analysis: true}            │
│ 15:30:47.345 │ transport:connect ● monitor_123                          │
│              │ Role: monitor  Capabilities: [observe, metrics]          │
└─[↑][↓] Navigate  [Enter] Details  [/] Search  [T] Jump to time ──────────┘
```

**Strengths:**
- Excellent for troubleshooting and forensics
- Rich temporal context and correlations
- Advanced filtering and search capabilities
- Perfect for understanding system behavior over time

**Use Cases:**
- Debugging complex interactions
- Performance analysis
- Audit trail investigation
- Understanding system patterns

**Technical Implementation:**
```python
class TimelineView(Container):
    def compose(self) -> ComposeResult:
        with Container(id="time-controls"):
            yield TimeNavigator()
            yield FilterControls()
        with ScrollableContainer(id="timeline"):
            yield EventTimeline()
        with Container(id="details"):
            yield EventDetails()
```

### Option C: Command Center 🏛️ **[RECOMMENDED]**

**Concept**: Comprehensive real-time operations center with live status, detailed monitoring, and action capabilities.

```
┌─ KSI Command Center ─────────────────────────────────────────────────────┐
│ ┌─Live Events─────────────────┐ ┌─Active Sessions──────────────────────┐ │
│ │ ● completion:request        │ │ 📊 Session fd5cacf7... (5 messages) │ │
│ │   client_abc "What is..."   │ │ 🔄 Duration: 5m 23s                 │ │
│ │ ● agent:spawn              │ │ 💰 Cost: $0.025                     │ │
│ │   admin_xyz researcher      │ │ ──────────────────────────────────── │ │
│ │ ● transport:connect        │ │ 🤖 Agent researcher (active)        │ │
│ │   monitor_123 [monitor]     │ │ 📍 State: processing                │ │
│ │ ● state:set                │ │ 🔗 Connected: 2m 45s                │ │
│ │   agent_abc status=active   │ │ ──────────────────────────────────── │ │
│ └─────────────────────────────┘ └──────────────────────────────────────┘ │
├─System Health────────────────────────────────────────────────────────────┤
│ 🟢 Daemon: Healthy  📊 Events: 1,234  💾 Memory: 45MB  🔌 Sockets: 8    │
│ ▓▓▓▓▓▓▓▓▓░ CPU 90%   ▓▓▓▓▓▓░░░░ Disk 60%   ▓▓▓▓▓▓▓▓▓▓ Net 100%         │
├─Event Details────────────────────────────────────────────────────────────┤
│ Selected: completion:request @ 15:30:45.123                              │
│ ┌─Request─────────────┐ ┌─Response────────────┐ ┌─Performance─────────┐  │
│ │ Client: event_abc   │ │ Status: success     │ │ Duration: 1.234s    │  │
│ │ Model: sonnet       │ │ Tokens: 150 → 45    │ │ API Time: 0.987s    │  │
│ │ Session: continuing │ │ Cost: $0.003        │ │ Queue Time: 0.247s  │  │
│ └─────────────────────┘ └─────────────────────┘ └─────────────────────┘  │
└─[Tab] Switch pane  [Enter] Drill down  [Esc] Back ───────────────────────┘
```

**Strengths:**
- Comprehensive real-time visibility
- Perfect balance of overview and detail
- Actionable insights with drill-down capability
- Professional operations center aesthetic
- Handles all event types simultaneously

**Use Cases:**
- Primary monitoring interface for all users
- Real-time system operations
- Performance monitoring
- Active troubleshooting

### Option D: Data Explorer 📊

**Concept**: Analytical interface optimized for data exploration, querying, and export.

```
┌─ Event Data Explorer ────────────────────────────────────────────────────┐
│ View: [Timeline▼] Filter: [completion:*] Since: [1h ago] Limit: [100]    │
├─────────────────────────────────────────────────────────────────────────┤
│ Time     │Event            │Client        │Status │Duration│Cost    │⚡│ │
│──────────┼─────────────────┼──────────────┼───────┼────────┼────────┼──│ │
│15:30:45.1│completion:req.. │event_client..│✅ ok  │ 1.234s │$0.003  │⚡│ │
│15:30:46.2│agent:spawn      │admin_xyz     │✅ ok  │ 0.045s │   -    │ │ │
│15:30:47.3│transport:conn.. │monitor_123   │✅ ok  │ 0.012s │   -    │ │ │
│15:30:48.4│state:set        │agent_abc     │✅ ok  │ 0.003s │   -    │ │ │
│15:30:49.5│message:publish  │coordinator   │✅ ok  │ 0.001s │   -    │ │ │
│15:30:50.6│completion:req.. │chat_client   │⚠️ slow│ 3.456s │$0.012  │⚡│ │
│15:30:51.7│conversation:exp.│export_tool   │✅ ok  │ 0.234s │   -    │ │ │
├─Event Details (completion:request @ 15:30:45.123)──────────────────────────┤
│ {                                                                        │
│   "prompt": "What is 2+2? Please explain the mathematical steps",       │
│   "model": "claude-3-5-sonnet",                                         │
│   "session_id": "fd5cacf7-ec8b-4838-90e8-1428646c6490",                │
│   "temperature": 0.7,                                                   │
│   "response": "The answer is 4. Here's the step-by-step calculation..." │
│ }                                                                        │
└─[Sort] Column  [Filter] Query  [Export] CSV  [Search] Text ──────────────┘
```

**Strengths:**
- Powerful querying and filtering
- Excellent for analysis and reporting
- Easy data export capabilities
- Familiar table-based interface

**Use Cases:**
- Data analysis and reporting
- Performance trending
- System auditing
- Cost analysis

## Recommended Implementation: Command Center

### Why Command Center is Optimal

1. **Comprehensive Coverage**: Shows all 6 event namespaces simultaneously
2. **Balanced Information Density**: Right amount of detail without overwhelming
3. **Actionable Interface**: Clear paths to drill down and investigate
4. **Professional Aesthetics**: Modern dashboard feel appropriate for operations
5. **Extensible Design**: Easy to add new capabilities as KSI evolves
6. **Performance Oriented**: Designed for real-time updates with historical context

## Technical Architecture

### Event-First Design Pattern

```python
# Clean MVC separation for maintainability and testability
class EventLogModel:          # Data layer - event log queries
class MonitorView:            # UI layer - display components  
class MonitorController:      # Logic layer - event routing
class MonitorApp:             # Main app - coordinates everything
```

### Core Components

#### 1. EventLogModel (Data Layer)
```python
class EventLogModel:
    """Pure data layer for event log queries"""
    
    async def get_recent_events(self, limit=100, patterns=None):
        """Fetch recent events with filtering"""
    
    async def get_system_health(self):
        """Get current system health metrics"""
    
    async def get_active_sessions(self):
        """Get active conversation sessions"""
    
    async def get_agent_status(self):
        """Get active agent information"""
    
    def subscribe_to_updates(self, callback):
        """Register for real-time updates"""
```

#### 2. MonitorView (UI Layer)
```python
class LiveEventsPane(Container):
    """Real-time event stream display"""
    
class ActiveSessionsPane(Container):
    """Active sessions and agents"""
    
class SystemHealthPane(Container):
    """System metrics and health indicators"""
    
class EventDetailsPane(Container):
    """Detailed view of selected events"""
```

#### 3. MonitorController (Logic Layer)
```python
class MonitorController:
    """Coordinates between model and view"""
    
    def __init__(self, model: EventLogModel, view: MonitorView):
        self.model = model
        self.view = view
    
    async def start_monitoring(self):
        """Initialize monitoring loop"""
    
    async def handle_event_selection(self, event):
        """Handle user selecting an event"""
    
    async def apply_filters(self, filters):
        """Apply user-defined filters"""
```

### Modern Textual Features Utilized

#### 1. CSS-First Styling
```css
/* Modern aesthetics with gradients and shadows */
.event-pane {
    background: linear-gradient(90deg, $surface 0%, $surface-lighten-1 100%);
    border: solid $primary;
    border-radius: 2;
}

.status-healthy {
    color: $success;
    text-style: bold;
}

.metric-critical {
    background: $error;
    color: $text-on-error;
    animation: pulse 2s ease-in-out infinite;
}
```

#### 2. Responsive Grid Layout
```python
class CommandCenterLayout(Container):
    """Responsive grid that adapts to terminal size"""
    
    CSS = """
    #main-grid {
        layout: grid;
        grid-size: 2 3;  /* 2 columns, 3 rows */
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr auto;
        height: 100%;
    }
    
    @media (max-width: 120) {
        #main-grid {
            grid-size: 1 4;  /* Stack vertically on narrow terminals */
            grid-columns: 1fr;
        }
    }
    """
```

#### 3. Rich Data Display
```python
class EventDataTable(DataTable):
    """High-performance event display with sorting"""
    
    def __init__(self):
        super().__init__()
        self.add_columns(
            "Time", "Event", "Client", "Status", "Duration", "Cost"
        )
        self.cursor_type = "row"
        self.zebra_stripes = True
```

#### 4. Focus Management
```python
class MonitorApp(App):
    """Proper keyboard navigation between panes"""
    
    BINDINGS = [
        ("tab", "next_pane", "Next Pane"),
        ("shift+tab", "prev_pane", "Previous Pane"), 
        ("f", "toggle_filter", "Filter"),
        ("enter", "drill_down", "Details"),
        ("/", "search", "Search"),
    ]
    
    def action_next_pane(self):
        """Cycle focus between panes"""
        self.screen.focus_next()
```

### Performance Optimizations

#### 1. Smart Update Strategy
```python
class EventStreamUpdater:
    """Efficient event stream updates"""
    
    def __init__(self):
        self.last_timestamp = 0.0
        self.update_batch = []
        self.update_timer = None
    
    async def process_events(self, events):
        """Batch updates for performance"""
        new_events = [e for e in events if e['timestamp'] > self.last_timestamp]
        
        if new_events:
            self.update_batch.extend(new_events)
            
            # Debounced updates - collect events for 100ms then update UI
            if self.update_timer:
                self.update_timer.cancel()
            self.update_timer = self.set_timer(0.1, self.flush_updates)
```

#### 2. Intelligent Caching
```python
class EventCache:
    """LRU cache for frequently accessed data"""
    
    def __init__(self, max_size=1000):
        self.cache = {}
        self.access_order = []
        self.max_size = max_size
    
    def get_event_details(self, event_id):
        """Cached event detail lookup"""
        if event_id in self.cache:
            self._update_access(event_id)
            return self.cache[event_id]
        
        # Fetch from model and cache
        details = self.model.get_event_details(event_id)
        self._add_to_cache(event_id, details)
        return details
```

### Event Type Handlers

#### 1. Completion Events
```python
class CompletionEventHandler:
    """Handle completion:* events with rich formatting"""
    
    def format_completion_request(self, event):
        client = event['client_id']
        prompt = self.truncate_prompt(event['data']['prompt'])
        model = event['data'].get('model', 'unknown')
        
        return f"[green]{client}[/] [cyan]{model}[/] {prompt}"
    
    def format_completion_metrics(self, event):
        duration = event['data'].get('duration_ms', 0) / 1000
        tokens = event['data'].get('tokens', {})
        cost = event['data'].get('cost', 0)
        
        return f"⏱️ {duration:.2f}s 🪙 {tokens} 💰 ${cost:.4f}"
```

#### 2. Agent Events  
```python
class AgentEventHandler:
    """Handle agent:* events"""
    
    def format_agent_spawn(self, event):
        agent_id = event['data']['agent_id'] 
        profile = event['data'].get('profile', 'default')
        
        return f"🤖 [bold]{agent_id}[/] profile=[cyan]{profile}[/]"
    
    def format_agent_status(self, event):
        # Show agent health, active tasks, resource usage
        pass
```

#### 3. System Events
```python
class SystemEventHandler:
    """Handle system:* events with health indicators"""
    
    def format_health_check(self, event):
        status = event['data']['status']
        emoji = "🟢" if status == "healthy" else "🔴"
        
        return f"{emoji} System {status}"
```

## User Experience Flows

### Primary Workflows

#### 1. Real-time Monitoring
```
User opens monitor → 
  Load last 500 events for context →
  Start real-time updates →
  Show live events in main pane →
  Update metrics and health indicators →
  Highlight anomalies and errors
```

#### 2. Troubleshooting Investigation
```
User notices error in live stream →
  Click event for details →
  Show full event data and context →
  Provide related events (same session/client) →
  Offer export and analysis options →
  Enable filtering to focus investigation
```

#### 3. Performance Analysis
```
User wants to analyze system performance →
  Switch to metrics view →
  Show duration trends and outliers →
  Highlight expensive operations →
  Provide cost breakdowns →
  Enable time-range analysis
```

### Keyboard Navigation
```
Tab/Shift+Tab  - Navigate between panes
Enter          - Drill down into selected item
Esc            - Go back/close details  
F              - Open filter dialog
/              - Open search dialog
R              - Refresh/reload data
E              - Export current view
H              - Toggle history mode
D              - Toggle detailed view
Q              - Quit application
?              - Show help
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [x] Event log system (completed)
- [ ] Basic UI framework with Command Center layout
- [ ] EventLogModel with essential queries
- [ ] Simple event display (completion and transport events)
- [ ] Real-time updates with basic polling

### Phase 2: Comprehensive Coverage (Week 2)  
- [ ] All 6 event namespace handlers
- [ ] System health monitoring
- [ ] Active sessions tracking
- [ ] Agent status monitoring
- [ ] Enhanced event formatting

### Phase 3: Advanced Features (Week 3)
- [ ] Filtering and search capabilities
- [ ] Historical data navigation
- [ ] Export functionality
- [ ] Performance analytics
- [ ] Alerting and notifications

### Phase 4: Polish & Optimization (Week 4)
- [ ] Performance optimizations
- [ ] CSS styling and animations
- [ ] Keyboard shortcuts and accessibility
- [ ] Error handling and edge cases
- [ ] Documentation and help system

## Integration with KSI Ecosystem

### ksi_client Extensions Needed

#### 1. Enhanced MonitorClient
```python
class MonitorClient(AdminBaseClient):
    """Extended monitoring capabilities"""
    
    async def get_system_metrics(self):
        """Get comprehensive system metrics"""
        
    async def get_performance_trends(self, window='1h'):
        """Get performance data over time window"""
        
    async def export_events(self, format='json', filters=None):
        """Export events in various formats"""
        
    async def subscribe_to_alerts(self, severity='warning'):
        """Real-time alerting for critical events"""
```

#### 2. New Monitoring Events  
```python
# Add to ksi_daemon/plugins/core/monitor.py
"monitor:metrics"     - Real-time system metrics
"monitor:alerts"      - Critical system alerts  
"monitor:trends"      - Performance trending data
"monitor:health"      - Comprehensive health check
```

### Data Export Capabilities
```python
class EventExporter:
    """Export monitoring data in multiple formats"""
    
    def export_csv(self, events, filename):
        """Export events as CSV for Excel analysis"""
        
    def export_json(self, events, filename):
        """Export events as JSON for programmatic use"""
        
    def export_markdown(self, events, filename):
        """Export events as markdown report"""
        
    def export_metrics_dashboard(self, timeframe):
        """Generate HTML dashboard with charts"""
```

## Security and Privacy Considerations

### Data Handling
- Never log sensitive prompt content in monitoring displays
- Truncate long prompts with option to view full content
- Mask or redact personally identifiable information
- Implement configurable data retention policies

### Access Control
- Monitor client requires admin privileges
- Audit monitor access and actions
- Rate limiting for event queries
- Secure data export with access logging

## Future Enhancements

### Advanced Analytics
- Machine learning for anomaly detection
- Predictive performance modeling
- Cost optimization recommendations
- Automated alerting with smart thresholds

### Collaboration Features
- Shared monitoring sessions
- Collaborative investigation tools
- Event annotations and bookmarking
- Team notifications and handoffs

### Integration Ecosystem
- Prometheus/Grafana metrics export
- Slack/Discord alert integration
- External monitoring system webhooks
- SIEM integration for security events

## Conclusion

The Command Center design provides the optimal balance of comprehensiveness, usability, and extensibility for KSI monitoring. By building on the solid foundation of the event log system with modern Textual best practices, we can create a world-class monitoring interface that grows with the KSI ecosystem while providing immediate value for system operators, developers, and administrators.

The event-first architecture ensures that every aspect of KSI daemon operation is visible and actionable, supporting both real-time operations and deep forensic analysis. The clean MVC separation and modern UI patterns make the system maintainable and extensible for future capabilities.

This design positions KSI's monitoring capabilities as a competitive advantage, providing visibility and control that enables confident operation of complex multi-agent AI systems at scale.
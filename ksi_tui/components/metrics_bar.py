"""
MetricsBar - Animated metrics display component for dashboards.

Features:
- Real-time metric updates with smooth animations
- Progress bars with color coding
- Sparkline graphs for trends
- Customizable metric types
- Responsive layout
"""

from typing import Optional, List, Dict, Any, Literal, Deque
from dataclasses import dataclass
from collections import deque
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, ProgressBar, Sparkline, Label
from textual.reactive import reactive
from textual.timer import Timer


MetricType = Literal["percentage", "count", "bytes", "rate", "currency"]


@dataclass
class Metric:
    """Represents a single metric."""
    name: str
    value: float
    unit: str
    type: MetricType
    max_value: Optional[float] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    
    @property
    def formatted_value(self) -> str:
        """Format the metric value for display."""
        if self.type == "percentage":
            return f"{self.value:.1f}%"
        elif self.type == "bytes":
            return self._format_bytes(self.value)
        elif self.type == "currency":
            return f"${self.value:,.2f}"
        elif self.type == "rate":
            return f"{self.value:.1f}/{self.unit}"
        else:  # count
            return f"{int(self.value):,}"
    
    def _format_bytes(self, bytes: float) -> str:
        """Format bytes in human-readable form."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f}{unit}"
            bytes /= 1024.0
        return f"{bytes:.1f}PB"
    
    @property
    def progress(self) -> float:
        """Calculate progress as a percentage."""
        if self.max_value and self.max_value > 0:
            return min(100, (self.value / self.max_value) * 100)
        elif self.type == "percentage":
            return min(100, self.value)
        else:
            # For unbounded metrics, assume 100% at some reasonable value
            return min(100, self.value)


class MetricDisplay(Container):
    """Individual metric display with progress bar and value."""
    
    def __init__(
        self,
        metric: Metric,
        show_progress: bool = True,
        show_sparkline: bool = False,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """
        Initialize a metric display.
        
        Args:
            metric: The metric to display
            show_progress: Whether to show a progress bar
            show_sparkline: Whether to show a sparkline graph
            name: Widget name
            id: Widget ID
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.metric = metric
        self.show_progress = show_progress
        self.show_sparkline = show_sparkline
        
        # History for sparkline
        self.history: Deque[float] = deque(maxlen=20)
        self.history.append(metric.value)
    
    def compose(self) -> ComposeResult:
        """Compose the metric display UI."""
        with Vertical(classes="metric-display"):
            # Header with icon, name, and value
            with Horizontal(classes="metric-header"):
                if self.metric.icon:
                    yield Static(self.metric.icon, classes="metric-icon")
                yield Label(self.metric.name, classes="metric-name")
                yield Static(
                    self.metric.formatted_value,
                    classes="metric-value",
                    id=f"value-{self.metric.name}"
                )
            
            # Progress bar
            if self.show_progress:
                progress_bar = ProgressBar(
                    total=100,
                    show_eta=False,
                    id=f"progress-{self.metric.name}"
                )
                progress_bar.advance(self.metric.progress)
                yield progress_bar
            
            # Sparkline
            if self.show_sparkline:
                yield Sparkline(
                    self.history,
                    id=f"sparkline-{self.metric.name}",
                    classes="metric-sparkline"
                )
    
    def update_metric(self, value: float) -> None:
        """Update the metric value with animation."""
        self.metric.value = value
        self.history.append(value)
        
        # Update value display
        value_widget = self.query_one(f"#value-{self.metric.name}", Static)
        value_widget.update(self.metric.formatted_value)
        
        # Update progress bar if shown
        if self.show_progress:
            progress = self.query_one(f"#progress-{self.metric.name}", ProgressBar)
            # Animate to new progress
            progress.progress = self.metric.progress
        
        # Update sparkline if shown
        if self.show_sparkline:
            sparkline = self.query_one(f"#sparkline-{self.metric.name}", Sparkline)
            sparkline.data = list(self.history)
            sparkline.refresh()


class MetricsBar(Container):
    """Container for displaying multiple metrics in a bar layout."""
    
    DEFAULT_LAYOUT = "horizontal"  # horizontal or vertical
    
    def __init__(
        self,
        metrics: Optional[List[Metric]] = None,
        layout: Literal["horizontal", "vertical"] = DEFAULT_LAYOUT,
        show_progress: bool = True,
        show_sparklines: bool = False,
        update_interval: float = 1.0,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """
        Initialize the metrics bar.
        
        Args:
            metrics: Initial list of metrics to display
            layout: Layout direction (horizontal or vertical)
            show_progress: Whether to show progress bars
            show_sparklines: Whether to show sparkline graphs
            update_interval: How often to request metric updates (seconds)
            name: Widget name
            id: Widget ID
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.metrics = metrics or []
        self.layout_type = layout
        self.show_progress = show_progress
        self.show_sparklines = show_sparklines
        self.update_interval = update_interval
        
        # Metric displays by name
        self._displays: Dict[str, MetricDisplay] = {}
        
        # Update timer
        self._update_timer: Optional[Timer] = None
        
        # Update callback
        self._update_callback = None
    
    def compose(self) -> ComposeResult:
        """Compose the metrics bar UI."""
        container_class = Horizontal if self.layout_type == "horizontal" else Vertical
        
        with container_class(classes=f"metrics-container metrics-{self.layout_type}"):
            for metric in self.metrics:
                display = MetricDisplay(
                    metric,
                    show_progress=self.show_progress,
                    show_sparkline=self.show_sparklines,
                    classes="metric-item"
                )
                self._displays[metric.name] = display
                yield display
    
    def add_metric(self, metric: Metric) -> None:
        """Add a new metric to the bar."""
        if metric.name not in self._displays:
            self.metrics.append(metric)
            display = MetricDisplay(
                metric,
                show_progress=self.show_progress,
                show_sparkline=self.show_sparklines,
                classes="metric-item"
            )
            self._displays[metric.name] = display
            self.mount(display)
    
    def update_metric(self, name: str, value: float) -> None:
        """Update a specific metric by name."""
        if name in self._displays:
            self._displays[name].update_metric(value)
    
    def update_metrics(self, updates: Dict[str, float]) -> None:
        """Update multiple metrics at once."""
        for name, value in updates.items():
            self.update_metric(name, value)
    
    def set_update_callback(self, callback) -> None:
        """Set a callback to fetch metric updates."""
        self._update_callback = callback
    
    def on_mount(self) -> None:
        """Start the update timer when mounted."""
        if self._update_callback and self.update_interval > 0:
            self._update_timer = self.set_interval(
                self.update_interval,
                self._fetch_updates
            )
    
    async def _fetch_updates(self) -> None:
        """Fetch metric updates from the callback."""
        if self._update_callback:
            try:
                updates = await self._update_callback()
                if isinstance(updates, dict):
                    self.update_metrics(updates)
            except Exception:
                # Ignore update errors
                pass
    
    def on_unmount(self) -> None:
        """Stop the update timer when unmounted."""
        if self._update_timer:
            self._update_timer.stop()


class QuickStats(MetricsBar):
    """Simplified metrics bar for common stats."""
    
    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """Initialize with common metrics."""
        common_metrics = [
            Metric("CPU", 0, "%", "percentage", 100, "green", "💻"),
            Metric("Memory", 0, "MB", "bytes", None, "blue", "🧠"),
            Metric("Messages", 0, "msg", "count", None, "cyan", "💬"),
            Metric("Tokens", 0, "tok", "count", None, "yellow", "🎯"),
            Metric("Cost", 0, "USD", "currency", None, "red", "💰"),
        ]
        
        super().__init__(
            metrics=common_metrics,
            layout="horizontal",
            show_progress=True,
            show_sparklines=False,
            name=name,
            id=id,
            classes=classes
        )


# CSS for metrics components
METRICS_CSS = """
/* Metrics bar container */
MetricsBar {
    height: auto;
    background: var(--surface0);
    border: round var(--surface1);
    padding: 1;
}

/* Layout variations */
.metrics-horizontal {
    layout: horizontal;
    height: 5;
}

.metrics-vertical {
    layout: vertical;
    width: 30;
}

/* Individual metric display */
.metric-item {
    padding: 0 1;
    height: 100%;
}

.metrics-horizontal .metric-item {
    width: 1fr;
    border-right: tall var(--surface1);
}

.metrics-horizontal .metric-item:last-child {
    border-right: none;
}

.metrics-vertical .metric-item {
    height: auto;
    width: 100%;
    border-bottom: tall var(--surface1);
    margin-bottom: 1;
}

/* Metric components */
.metric-header {
    height: 1;
    margin-bottom: 1;
}

.metric-icon {
    width: 2;
    text-align: center;
}

.metric-name {
    width: 1fr;
    text-style: bold;
    color: var(--subtext1);
}

.metric-value {
    width: auto;
    text-align: right;
    color: var(--text);
    text-style: bold;
}

/* Progress bars */
.metric-display ProgressBar {
    height: 1;
    width: 100%;
}

.metric-display ProgressBar Bar {
    background: var(--surface2);
}

.metric-display ProgressBar PercentageStatus {
    text-style: dim;
}

/* Sparklines */
.metric-sparkline {
    height: 2;
    margin-top: 1;
    color: var(--blue);
}

/* Quick stats specific */
QuickStats {
    height: 6;
    dock: top;
}
"""
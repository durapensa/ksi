"""
Catppuccin-inspired theme for KSI TUI applications.

A soothing pastel theme that's easy on the eyes.
Based on Catppuccin Mocha variant.
"""

# Catppuccin Mocha color palette
CATPPUCCIN_MOCHA = {
    # Base colors
    "rosewater": "#f5e0dc",
    "flamingo": "#f2cdcd",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
    "red": "#f38ba8",
    "maroon": "#eba0ac",
    "peach": "#fab387",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "teal": "#94e2d5",
    "sky": "#89dceb",
    "sapphire": "#74c7ec",
    "blue": "#89b4fa",
    "lavender": "#b4befe",
    "text": "#cdd6f4",
    "subtext1": "#bac2de",
    "subtext0": "#a6adc8",
    "overlay2": "#9399b2",
    "overlay1": "#7f849c",
    "overlay0": "#6c7086",
    "surface2": "#585b70",
    "surface1": "#45475a",
    "surface0": "#313244",
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
}

# CSS for Catppuccin theme
CATPPUCCIN_CSS = """
/* Catppuccin Mocha Theme for KSI TUI */
/* Using Textual CSS syntax with color variables */

/* Base application styling */
App {
    background: var(--base);
    color: var(--text);
}

/* Headers and titles */
.header {
    background: var(--mantle);
    color: var(--text);
    text-style: bold;
    border-bottom: tall var(--surface0);
}

.title {
    color: var(--lavender);
    text-style: bold;
}

/* Panels and containers */
.panel {
    background: var(--mantle);
    border: round var(--surface1);
    padding: 1;
}

.panel-header {
    background: var(--surface0);
    color: var(--subtext1);
    text-style: bold;
    padding: 0 1;
    height: 1;
}

/* Messages and chat bubbles - simplified to avoid display issues */
.message {
}

.message-user {
    background: var(--surface1);
}

.message-assistant {
    background: var(--surface0);  
}

.message-system {
    background: var(--surface0);
}

.message-error {
    background: var(--surface0);
    color: var(--red);
}

/* Input fields */
Input {
    background: var(--surface0);
    border: tall var(--surface1);
    padding: 0 1;
}

Input:focus {
    border: tall var(--lavender);
}

/* Buttons */
Button {
    background: var(--surface1);
    color: var(--text);
    border: tall var(--surface2);
    padding: 0 2;
}

Button:hover {
    background: var(--surface2);
    border: tall var(--overlay0);
}

Button:focus {
    background: var(--surface2);
    border: tall var(--lavender);
}

Button.-primary {
    background: var(--blue);
    color: var(--base);
    border: tall var(--blue);
}

Button.-primary:hover {
    background: var(--sapphire);
    border: tall var(--sapphire);
}

Button.-success {
    background: var(--green);
    color: var(--base);
}

Button.-warning {
    background: var(--yellow);
    color: var(--base);
}

Button.-error {
    background: var(--red);
    color: var(--base);
}

/* Status indicators */
.status-online {
    color: var(--green);
}

.status-offline {
    color: var(--overlay0);
}

.status-error {
    color: var(--red);
}

.status-warning {
    color: var(--yellow);
}

/* Scrollbars */
ScrollBar {
    background: var(--surface0);
}

ScrollBarThumb {
    background: var(--surface2);
}

ScrollBarThumb:hover {
    background: var(--overlay0);
}

/* Lists and trees */
ListView {
    background: var(--mantle);
}

ListItem {
    padding: 0 1;
}

ListItem:hover {
    background: var(--surface0);
}

ListItem.-selected {
    background: var(--surface1);
    color: var(--lavender);
}

Tree {
    background: var(--mantle);
}

/* DataTable */
DataTable {
    background: var(--mantle);
}

DataTable > .datatable--header {
    background: var(--surface0);
    color: var(--subtext1);
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: var(--surface1);
    color: var(--text);
}

DataTable > .datatable--hover {
    background: var(--surface0);
}

DataTable > .datatable--fixed {
    background: var(--surface0);
    color: var(--overlay2);
}

/* Tabs */
Tabs {
    background: var(--mantle);
}

Tab {
    padding: 0 2;
}

Tab.-active {
    background: var(--surface0);
    color: var(--lavender);
    text-style: bold;
}

/* Footer */
Footer {
    background: var(--crust);
    color: var(--subtext0);
}

/* Notifications */
.notification {
    background: var(--surface1);
    border: tall var(--overlay0);
    padding: 1;
}

.notification-info {
    border: tall var(--blue);
}

.notification-success {
    border: tall var(--green);
}

.notification-warning {
    border: tall var(--yellow);
}

.notification-error {
    border: tall var(--red);
}

/* Code and syntax highlighting */
.syntax {
    background: var(--mantle);
    border: round var(--surface0);
    padding: 1;
}

.syntax-keyword {
    color: var(--mauve);
    text-style: bold;
}

.syntax-string {
    color: var(--green);
}

.syntax-number {
    color: var(--peach);
}

.syntax-comment {
    color: var(--overlay0);
    text-style: italic;
}

.syntax-function {
    color: var(--blue);
}

.syntax-class {
    color: var(--yellow);
}

/* Animation alternatives (Textual doesn't support @keyframes) */
.fade-in {
    opacity: 80%;
}

.slide-in {
    /* Simple alternative without animation */
}

/* Utility classes */
.dim {
    opacity: 70%;
}

.muted {
    color: var(--subtext0);
}

.bold {
    text-style: bold;
}

.italic {
    text-style: italic;
}

.center {
    text-align: center;
}

.right {
    text-align: right;
}

/* Spacing utilities */
.mt-1 { margin-top: 1; }
.mt-2 { margin-top: 2; }
.mb-1 { margin-bottom: 1; }
.mb-2 { margin-bottom: 2; }
.mx-1 { margin: 0 1; }
.my-1 { margin: 1 0; }
.p-1 { padding: 1; }
.p-2 { padding: 2; }
"""

def get_theme_css() -> str:
    """Get the complete Catppuccin theme CSS with variables replaced."""
    css = CATPPUCCIN_CSS
    
    # Replace all var() references with actual colors
    for name, color in CATPPUCCIN_MOCHA.items():
        css = css.replace(f"var(--{name})", color)
    
    return css

def get_color(name: str) -> str:
    """Get a specific color from the Catppuccin palette."""
    return CATPPUCCIN_MOCHA.get(name, "#ffffff")
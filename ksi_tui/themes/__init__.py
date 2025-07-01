"""
KSI TUI Theme System

Provides consistent theming across all KSI TUI applications.
"""

from typing import Dict, Optional

from .catppuccin import get_theme_css, get_color, CATPPUCCIN_MOCHA

# Available themes
THEMES = {
    "catppuccin": {
        "name": "Catppuccin Mocha",
        "css_func": get_theme_css,
        "colors": CATPPUCCIN_MOCHA,
    }
}

# Default theme
DEFAULT_THEME = "catppuccin"


class ThemeManager:
    """Manages themes for KSI TUI applications."""
    
    def __init__(self, theme: str = DEFAULT_THEME):
        """Initialize with a specific theme."""
        self._current_theme = theme
        self._custom_css = ""
    
    @property
    def current_theme(self) -> str:
        """Get the current theme name."""
        return self._current_theme
    
    @property
    def css(self) -> str:
        """Get the complete CSS for the current theme."""
        theme_data = THEMES.get(self._current_theme, {})
        css_func = theme_data.get("css_func")
        theme_css = css_func() if css_func else ""
        return f"{theme_css}\n{self._custom_css}" if self._custom_css else theme_css
    
    def get_color(self, name: str) -> str:
        """Get a specific color from the current theme."""
        colors = THEMES.get(self._current_theme, {}).get("colors", {})
        return colors.get(name, "#ffffff")
    
    def set_theme(self, theme: str) -> bool:
        """Set the current theme."""
        if theme in THEMES:
            self._current_theme = theme
            return True
        return False
    
    def add_custom_css(self, css: str) -> None:
        """Add custom CSS to be appended to the theme."""
        self._custom_css = css
    
    def list_themes(self) -> Dict[str, str]:
        """List available themes."""
        return {k: v["name"] for k, v in THEMES.items()}


# Global theme manager instance
theme_manager = ThemeManager()

# Convenience exports
__all__ = [
    "ThemeManager",
    "theme_manager",
    "THEMES",
    "DEFAULT_THEME",
    "get_color",
]
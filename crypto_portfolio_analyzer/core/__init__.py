"""
Core components for the Crypto Portfolio Analyzer.

This module contains the fundamental building blocks including context management,
plugin system, configuration, and event handling.
"""

from crypto_portfolio_analyzer.core.context import AppContext
from crypto_portfolio_analyzer.core.plugin_manager import PluginManager
from crypto_portfolio_analyzer.core.config import ConfigManager
from crypto_portfolio_analyzer.core.events import EventBus

__all__ = [
    "AppContext",
    "PluginManager",
    "ConfigManager", 
    "EventBus",
]

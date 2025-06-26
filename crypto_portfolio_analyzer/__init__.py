"""
Crypto Portfolio Analyzer - A sophisticated CLI tool for cryptocurrency portfolio management.

This package provides a meta-driven CLI with plugin architecture, real-time price fetching,
portfolio analytics, and comprehensive reporting capabilities.
"""

__version__ = "0.1.0"
__author__ = "Crypto Portfolio Analyzer Team"
__email__ = "team@cryptoportfolio.dev"
__license__ = "MIT"

# Core imports for public API
from crypto_portfolio_analyzer.core.context import AppContext
from crypto_portfolio_analyzer.core.plugin_manager import PluginManager
from crypto_portfolio_analyzer.core.config import ConfigManager

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "AppContext",
    "PluginManager", 
    "ConfigManager",
]

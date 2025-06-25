"""
Plugin system for the Crypto Portfolio Analyzer.

This package contains core plugins and provides the base infrastructure
for plugin development and management.
"""

from crypto_portfolio_analyzer.plugins.portfolio import PortfolioPlugin
from crypto_portfolio_analyzer.plugins.config import ConfigPlugin

__all__ = [
    "PortfolioPlugin",
    "ConfigPlugin",
]

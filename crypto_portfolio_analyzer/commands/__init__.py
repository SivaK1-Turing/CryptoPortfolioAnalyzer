"""
Command modules for the Crypto Portfolio Analyzer CLI.

This package contains all the command implementations organized by functionality.
Commands are automatically discovered and registered through entry points.
"""

from crypto_portfolio_analyzer.commands.portfolio import portfolio_group
from crypto_portfolio_analyzer.commands.config import config_group

__all__ = [
    "portfolio_group",
    "config_group",
]

"""
Core portfolio management plugin.

This plugin provides the core portfolio management functionality including
holdings tracking, value calculation, and basic analytics.
"""

import logging
from typing import Any, Dict

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin
from crypto_portfolio_analyzer.core.events import EventType

logger = logging.getLogger(__name__)


class PortfolioPlugin(BasePlugin):
    """
    Core portfolio management plugin.
    
    Provides essential portfolio functionality including holdings management,
    value tracking, and basic analytics capabilities.
    """
    
    __version__ = "1.0.0"
    __author__ = "Crypto Portfolio Analyzer Team"
    
    def __init__(self, name: str = "portfolio"):
        super().__init__(name)
        self.holdings = {}
        self.total_value = 0.0
        self.last_update = None
    
    async def initialize(self) -> None:
        """Initialize the portfolio plugin."""
        logger.info("Initializing portfolio plugin")
        
        # Load existing portfolio data (in real implementation, this would load from database)
        await self._load_portfolio_data()
        
        logger.info(f"Portfolio plugin initialized with {len(self.holdings)} holdings")
    
    async def teardown(self) -> None:
        """Clean up the portfolio plugin."""
        logger.info("Shutting down portfolio plugin")
        
        # Save portfolio data (in real implementation, this would save to database)
        await self._save_portfolio_data()
        
        logger.info("Portfolio plugin shutdown complete")
    
    async def _load_portfolio_data(self) -> None:
        """Load portfolio data from storage."""
        # In a real implementation, this would load from a database or file
        # For now, we'll use sample data
        self.holdings = {
            "BTC": {"amount": 0.5, "avg_price": 30000, "current_price": 30000},
            "ETH": {"amount": 2.0, "avg_price": 1600, "current_price": 1600},
            "ADA": {"amount": 1000, "avg_price": 0.45, "current_price": 0.45},
        }
        
        await self._calculate_total_value()
        logger.debug(f"Loaded portfolio data: {len(self.holdings)} holdings")
    
    async def _save_portfolio_data(self) -> None:
        """Save portfolio data to storage."""
        # In a real implementation, this would save to a database or file
        logger.debug(f"Saved portfolio data: {len(self.holdings)} holdings")
    
    async def _calculate_total_value(self) -> None:
        """Calculate total portfolio value."""
        self.total_value = sum(
            holding["amount"] * holding["current_price"]
            for holding in self.holdings.values()
        )
        logger.debug(f"Total portfolio value: ${self.total_value:,.2f}")
    
    async def add_holding(self, symbol: str, amount: float, price: float = None) -> bool:
        """
        Add a holding to the portfolio.
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            amount: Amount to add
            price: Purchase price (if None, uses current market price)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            symbol = symbol.upper()
            
            if symbol in self.holdings:
                # Update existing holding
                existing = self.holdings[symbol]
                total_amount = existing["amount"] + amount
                
                if price is not None:
                    # Calculate new average price
                    total_cost = (existing["amount"] * existing["avg_price"]) + (amount * price)
                    new_avg_price = total_cost / total_amount
                    existing["avg_price"] = new_avg_price
                
                existing["amount"] = total_amount
            else:
                # Add new holding
                current_price = price if price is not None else 0.0  # In real implementation, fetch current price
                self.holdings[symbol] = {
                    "amount": amount,
                    "avg_price": current_price,
                    "current_price": current_price
                }
            
            await self._calculate_total_value()
            logger.info(f"Added {amount} {symbol} to portfolio")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add holding {symbol}: {e}")
            return False
    
    async def remove_holding(self, symbol: str, amount: float) -> bool:
        """
        Remove a holding from the portfolio.
        
        Args:
            symbol: Cryptocurrency symbol
            amount: Amount to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            symbol = symbol.upper()
            
            if symbol not in self.holdings:
                logger.warning(f"Symbol {symbol} not found in portfolio")
                return False
            
            holding = self.holdings[symbol]
            
            if holding["amount"] < amount:
                logger.warning(f"Insufficient {symbol} balance: {holding['amount']} < {amount}")
                return False
            
            holding["amount"] -= amount
            
            # Remove holding if amount becomes zero
            if holding["amount"] == 0:
                del self.holdings[symbol]
                logger.info(f"Removed {symbol} from portfolio (zero balance)")
            else:
                logger.info(f"Reduced {symbol} holding by {amount}")
            
            await self._calculate_total_value()
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove holding {symbol}: {e}")
            return False
    
    def get_holdings(self) -> Dict[str, Dict[str, float]]:
        """Get all current holdings."""
        return self.holdings.copy()
    
    def get_holding(self, symbol: str) -> Dict[str, float]:
        """Get a specific holding."""
        return self.holdings.get(symbol.upper(), {})
    
    def get_total_value(self) -> float:
        """Get total portfolio value."""
        return self.total_value
    
    async def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for holdings.
        
        Args:
            prices: Dictionary of symbol -> price mappings
        """
        updated_count = 0
        
        for symbol, price in prices.items():
            symbol = symbol.upper()
            if symbol in self.holdings:
                self.holdings[symbol]["current_price"] = price
                updated_count += 1
        
        if updated_count > 0:
            await self._calculate_total_value()
            logger.info(f"Updated prices for {updated_count} holdings")
    
    async def on_command_start(self, command_name: str, context: Dict[str, Any]) -> None:
        """Handle command start events."""
        if command_name.startswith('portfolio'):
            logger.debug(f"Portfolio command started: {command_name}")
    
    async def on_command_end(self, command_name: str, context: Dict[str, Any], result: Any) -> None:
        """Handle command end events."""
        if command_name.startswith('portfolio'):
            logger.debug(f"Portfolio command completed: {command_name}")
    
    async def on_command_error(self, command_name: str, context: Dict[str, Any], error: Exception) -> None:
        """Handle command error events."""
        if command_name.startswith('portfolio'):
            logger.error(f"Portfolio command failed: {command_name} - {error}")
    
    def get_info(self):
        """Get plugin information."""
        info = super().get_info()
        info.description = "Core portfolio management functionality"
        return info

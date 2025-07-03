#!/usr/bin/env python3
"""
Basic Price Monitoring Example

This example demonstrates how to set up basic real-time price monitoring
using the Crypto Portfolio Analyzer streaming system.
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime

from crypto_portfolio_analyzer.streaming import (
    PriceFeedManager, PriceFeedProvider, PriceUpdate
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceMonitor:
    """Simple price monitoring class."""
    
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.price_feed_manager = PriceFeedManager()
        self.latest_prices = {}
        self.price_history = {}
        
    async def setup(self, provider: PriceFeedProvider = PriceFeedProvider.MOCK):
        """Set up the price monitoring system."""
        logger.info(f"Setting up price monitoring for {self.symbols}")
        
        # Add price feed provider
        self.price_feed_manager.add_provider(
            provider=provider,
            symbols=self.symbols,
            is_primary=True
        )
        
        # Add price update handler
        self.price_feed_manager.add_handler(self.handle_price_update)
        
        logger.info(f"Price monitoring setup complete with {provider.value} provider")
    
    def handle_price_update(self, update: PriceUpdate):
        """Handle incoming price updates."""
        # Store latest price
        self.latest_prices[update.symbol] = update
        
        # Add to history
        if update.symbol not in self.price_history:
            self.price_history[update.symbol] = []
        
        self.price_history[update.symbol].append({
            'timestamp': update.timestamp,
            'price': update.price,
            'change_24h': update.change_24h,
            'change_percent_24h': update.change_percent_24h
        })
        
        # Keep only last 100 entries
        if len(self.price_history[update.symbol]) > 100:
            self.price_history[update.symbol] = self.price_history[update.symbol][-100:]
        
        # Log the update
        change_str = ""
        if update.change_percent_24h is not None:
            change_str = f" ({update.change_percent_24h:+.2f}%)"
        
        logger.info(
            f"{update.symbol}: ${update.price:.2f}{change_str} "
            f"[{update.source.value}] at {update.timestamp.strftime('%H:%M:%S')}"
        )
    
    async def start(self):
        """Start price monitoring."""
        logger.info("Starting price monitoring...")
        await self.price_feed_manager.start()
        logger.info("Price monitoring started")
    
    async def stop(self):
        """Stop price monitoring."""
        logger.info("Stopping price monitoring...")
        await self.price_feed_manager.stop()
        logger.info("Price monitoring stopped")
    
    def get_latest_price(self, symbol: str) -> PriceUpdate | None:
        """Get the latest price for a symbol."""
        return self.latest_prices.get(symbol)
    
    def get_price_history(self, symbol: str, limit: int = 10) -> list[dict]:
        """Get recent price history for a symbol."""
        history = self.price_history.get(symbol, [])
        return history[-limit:] if history else []
    
    def print_summary(self):
        """Print a summary of current prices."""
        print("\n" + "="*60)
        print("CURRENT PRICES SUMMARY")
        print("="*60)
        
        for symbol in self.symbols:
            latest = self.get_latest_price(symbol)
            if latest:
                change_str = ""
                if latest.change_percent_24h is not None:
                    change_str = f" ({latest.change_percent_24h:+.2f}%)"
                
                print(f"{symbol:>6}: ${latest.price:>10.2f}{change_str}")
            else:
                print(f"{symbol:>6}: No data available")
        
        print("="*60)


async def main():
    """Main function demonstrating basic price monitoring."""
    # Symbols to monitor
    symbols = ["BTC", "ETH", "ADA"]
    
    # Create price monitor
    monitor = PriceMonitor(symbols)
    
    try:
        # Set up monitoring with mock provider (for demo)
        await monitor.setup(PriceFeedProvider.MOCK)
        
        # Start monitoring
        await monitor.start()
        
        # Monitor for 30 seconds
        logger.info("Monitoring prices for 30 seconds...")
        await asyncio.sleep(30)
        
        # Print summary
        monitor.print_summary()
        
        # Show price history for BTC
        print("\nBTC Price History (last 5 updates):")
        history = monitor.get_price_history("BTC", 5)
        for entry in history:
            timestamp = entry['timestamp'].strftime('%H:%M:%S')
            price = entry['price']
            change = entry.get('change_percent_24h', 0) or 0
            print(f"  {timestamp}: ${price:.2f} ({change:+.2f}%)")
        
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {e}")
    finally:
        # Clean up
        await monitor.stop()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())

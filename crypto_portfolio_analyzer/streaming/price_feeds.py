"""Live price feed integration for real-time cryptocurrency data."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from decimal import Decimal
import time

from ..data.models import CryptocurrencyPrice, DataSource
from .manager import StreamManager, StreamConfig

logger = logging.getLogger(__name__)


class PriceFeedProvider(Enum):
    """Supported price feed providers."""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    MOCK = "mock"  # For testing


@dataclass
class PriceUpdate:
    """Real-time price update data."""
    
    symbol: str
    price: Decimal
    volume_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: DataSource = DataSource.BINANCE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "price": float(self.price),
            "volume_24h": float(self.volume_24h) if self.volume_24h else None,
            "change_24h": float(self.change_24h) if self.change_24h else None,
            "change_percent_24h": self.change_percent_24h,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value
        }


class BasePriceFeed:
    """Base class for price feed implementations."""
    
    def __init__(self, provider: PriceFeedProvider, symbols: List[str]):
        self.provider = provider
        self.symbols = set(symbols)
        self.handlers: Set[Callable[[PriceUpdate], None]] = set()
        self._running = False
        
    async def start(self):
        """Start the price feed."""
        self._running = True
        logger.info(f"Started {self.provider.value} price feed for {len(self.symbols)} symbols")
    
    async def stop(self):
        """Stop the price feed."""
        self._running = False
        logger.info(f"Stopped {self.provider.value} price feed")
    
    def add_handler(self, handler: Callable[[PriceUpdate], None]):
        """Add price update handler."""
        self.handlers.add(handler)
    
    def remove_handler(self, handler: Callable[[PriceUpdate], None]):
        """Remove price update handler."""
        self.handlers.discard(handler)
    
    def add_symbol(self, symbol: str):
        """Add symbol to track."""
        self.symbols.add(symbol)
    
    def remove_symbol(self, symbol: str):
        """Remove symbol from tracking."""
        self.symbols.discard(symbol)
    
    async def _notify_handlers(self, update: PriceUpdate):
        """Notify all handlers of price update."""
        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(update))
                else:
                    handler(update)
            except Exception as e:
                logger.error(f"Error in price update handler: {e}")


class BinancePriceFeed(BasePriceFeed):
    """Binance WebSocket price feed."""
    
    def __init__(self, symbols: List[str]):
        super().__init__(PriceFeedProvider.BINANCE, symbols)
        self.stream_manager: Optional[StreamManager] = None
        
    async def start(self):
        """Start Binance price feed."""
        await super().start()
        
        self.stream_manager = StreamManager()
        await self.stream_manager.start()
        
        # Create stream for each symbol
        for symbol in self.symbols:
            stream_config = StreamConfig(
                stream_id=f"binance_{symbol.lower()}",
                url=f"wss://stream.binance.com:9443/ws/{symbol.lower()}usdt@ticker",
                symbols=[symbol],
                reconnect_attempts=5,
                heartbeat_interval=30.0
            )
            
            await self.stream_manager.add_stream(stream_config)
            
        # Add global handler for price updates
        self.stream_manager.add_global_handler(self._handle_binance_message)
    
    async def stop(self):
        """Stop Binance price feed."""
        if self.stream_manager:
            await self.stream_manager.stop()
        await super().stop()
    
    async def _handle_binance_message(self, stream_id: str, data: Dict[str, Any]):
        """Handle incoming Binance WebSocket message."""
        try:
            if "s" in data and "c" in data:  # Symbol and close price
                symbol = data["s"].replace("USDT", "")
                
                update = PriceUpdate(
                    symbol=symbol,
                    price=Decimal(data["c"]),
                    volume_24h=Decimal(data.get("v", "0")),
                    change_24h=Decimal(data.get("P", "0")),
                    change_percent_24h=float(data.get("P", "0")),
                    source=DataSource.BINANCE
                )
                
                await self._notify_handlers(update)
                
        except Exception as e:
            logger.error(f"Error processing Binance message: {e}")


class CoinbasePriceFeed(BasePriceFeed):
    """Coinbase WebSocket price feed."""
    
    def __init__(self, symbols: List[str]):
        super().__init__(PriceFeedProvider.COINBASE, symbols)
        self.stream_manager: Optional[StreamManager] = None
        
    async def start(self):
        """Start Coinbase price feed."""
        await super().start()
        
        self.stream_manager = StreamManager()
        await self.stream_manager.start()
        
        # Coinbase uses a single connection with subscription messages
        stream_config = StreamConfig(
            stream_id="coinbase_feed",
            url="wss://ws-feed.pro.coinbase.com",
            symbols=list(self.symbols),
            reconnect_attempts=5,
            heartbeat_interval=30.0
        )
        
        await self.stream_manager.add_stream(stream_config)
        self.stream_manager.add_global_handler(self._handle_coinbase_message)
        
        # Send subscription message
        subscribe_msg = {
            "type": "subscribe",
            "product_ids": [f"{symbol}-USD" for symbol in self.symbols],
            "channels": ["ticker"]
        }
        
        await self.stream_manager.send_to_stream("coinbase_feed", subscribe_msg)
    
    async def stop(self):
        """Stop Coinbase price feed."""
        if self.stream_manager:
            await self.stream_manager.stop()
        await super().stop()
    
    async def _handle_coinbase_message(self, stream_id: str, data: Dict[str, Any]):
        """Handle incoming Coinbase WebSocket message."""
        try:
            if data.get("type") == "ticker" and "product_id" in data:
                symbol = data["product_id"].replace("-USD", "")
                
                update = PriceUpdate(
                    symbol=symbol,
                    price=Decimal(data["price"]),
                    volume_24h=Decimal(data.get("volume_24h", "0")),
                    change_24h=Decimal(data.get("open_24h", "0")) - Decimal(data["price"]),
                    source=DataSource.COINBASE
                )
                
                await self._notify_handlers(update)
                
        except Exception as e:
            logger.error(f"Error processing Coinbase message: {e}")


class MockPriceFeed(BasePriceFeed):
    """Mock price feed for testing."""
    
    def __init__(self, symbols: List[str]):
        super().__init__(PriceFeedProvider.MOCK, symbols)
        self._task: Optional[asyncio.Task] = None
        self._base_prices = {
            "BTC": Decimal("50000"),
            "ETH": Decimal("3000"),
            "ADA": Decimal("1.50"),
            "DOT": Decimal("25.00"),
            "LINK": Decimal("20.00")
        }
        
    async def start(self):
        """Start mock price feed."""
        await super().start()
        self._task = asyncio.create_task(self._generate_mock_prices())
    
    async def stop(self):
        """Stop mock price feed."""
        if self._task:
            self._task.cancel()
        await super().stop()
    
    async def _generate_mock_prices(self):
        """Generate mock price updates."""
        import random
        
        while self._running:
            try:
                for symbol in self.symbols:
                    if symbol in self._base_prices:
                        # Generate random price movement
                        base_price = self._base_prices[symbol]
                        change_percent = random.uniform(-0.05, 0.05)  # ±5%
                        new_price = base_price * Decimal(str(1 + change_percent))
                        
                        update = PriceUpdate(
                            symbol=symbol,
                            price=new_price,
                            volume_24h=Decimal(random.uniform(1000000, 10000000)),
                            change_percent_24h=change_percent * 100,
                            source=DataSource.MOCK
                        )
                        
                        await self._notify_handlers(update)
                        
                        # Update base price for next iteration
                        self._base_prices[symbol] = new_price
                
                await asyncio.sleep(1)  # Update every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating mock prices: {e}")


class PriceFeedManager:
    """Manager for multiple price feeds with fallback mechanisms."""
    
    def __init__(self):
        self.feeds: Dict[PriceFeedProvider, BasePriceFeed] = {}
        self.primary_provider: Optional[PriceFeedProvider] = None
        self.fallback_providers: List[PriceFeedProvider] = []
        self.symbols: Set[str] = set()
        self.handlers: Set[Callable[[PriceUpdate], None]] = set()
        self._running = False
        self._last_update_times: Dict[str, datetime] = {}
        self._fallback_task: Optional[asyncio.Task] = None
        
    def add_provider(self, provider: PriceFeedProvider, symbols: List[str], 
                    is_primary: bool = False):
        """Add a price feed provider."""
        if provider == PriceFeedProvider.BINANCE:
            feed = BinancePriceFeed(symbols)
        elif provider == PriceFeedProvider.COINBASE:
            feed = CoinbasePriceFeed(symbols)
        elif provider == PriceFeedProvider.MOCK:
            feed = MockPriceFeed(symbols)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        feed.add_handler(self._handle_price_update)
        self.feeds[provider] = feed
        self.symbols.update(symbols)
        
        if is_primary:
            self.primary_provider = provider
        else:
            self.fallback_providers.append(provider)
            
        logger.info(f"Added {provider.value} price feed with {len(symbols)} symbols")
    
    def add_handler(self, handler: Callable[[PriceUpdate], None]):
        """Add price update handler."""
        self.handlers.add(handler)
    
    def remove_handler(self, handler: Callable[[PriceUpdate], None]):
        """Remove price update handler."""
        self.handlers.discard(handler)
    
    async def start(self):
        """Start all price feeds."""
        if self._running:
            return
            
        self._running = True
        
        # Start primary provider first
        if self.primary_provider and self.primary_provider in self.feeds:
            await self.feeds[self.primary_provider].start()
        
        # Start fallback providers
        for provider in self.fallback_providers:
            if provider in self.feeds:
                await self.feeds[provider].start()
        
        # Start fallback monitoring
        self._fallback_task = asyncio.create_task(self._monitor_fallback())
        
        logger.info(f"Started price feed manager with {len(self.feeds)} providers")
    
    async def stop(self):
        """Stop all price feeds."""
        if not self._running:
            return
            
        self._running = False
        
        if self._fallback_task:
            self._fallback_task.cancel()
        
        for feed in self.feeds.values():
            await feed.stop()
            
        logger.info("Stopped price feed manager")
    
    async def _handle_price_update(self, update: PriceUpdate):
        """Handle price update from any provider."""
        # Update last seen time
        self._last_update_times[update.symbol] = update.timestamp
        
        # Notify handlers
        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(update))
                else:
                    handler(update)
            except Exception as e:
                logger.error(f"Error in price update handler: {e}")
    
    async def _monitor_fallback(self):
        """Monitor primary feed and activate fallback if needed."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = datetime.now(timezone.utc)
                stale_symbols = []
                
                for symbol in self.symbols:
                    last_update = self._last_update_times.get(symbol)
                    if last_update:
                        time_since_update = (current_time - last_update).total_seconds()
                        if time_since_update > 60:  # No update for 1 minute
                            stale_symbols.append(symbol)
                
                if stale_symbols:
                    logger.warning(f"Stale price data for symbols: {stale_symbols}")
                    # Could implement fallback logic here
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in fallback monitor: {e}")
    
    def get_last_update_time(self, symbol: str) -> Optional[datetime]:
        """Get last update time for a symbol."""
        return self._last_update_times.get(symbol)
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        status = {}
        for provider, feed in self.feeds.items():
            status[provider.value] = {
                "running": feed._running,
                "symbols": list(feed.symbols),
                "handler_count": len(feed.handlers)
            }
        return status

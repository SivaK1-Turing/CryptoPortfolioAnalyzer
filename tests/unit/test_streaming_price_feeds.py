"""Tests for price feed integration."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from crypto_portfolio_analyzer.streaming.price_feeds import (
    PriceFeedManager, PriceFeedProvider, PriceUpdate, BasePriceFeed,
    BinancePriceFeed, CoinbasePriceFeed, MockPriceFeed
)
from crypto_portfolio_analyzer.data.models import DataSource


class TestPriceUpdate:
    """Test PriceUpdate dataclass."""
    
    def test_price_update_creation(self):
        """Test creating a price update."""
        update = PriceUpdate(
            symbol="BTC",
            price=Decimal("50000.00"),
            volume_24h=Decimal("1000000"),
            change_24h=Decimal("1000"),
            change_percent_24h=2.5,
            source=DataSource.BINANCE
        )
        
        assert update.symbol == "BTC"
        assert update.price == Decimal("50000.00")
        assert update.volume_24h == Decimal("1000000")
        assert update.change_24h == Decimal("1000")
        assert update.change_percent_24h == 2.5
        assert update.source == DataSource.BINANCE
        assert isinstance(update.timestamp, datetime)
    
    def test_price_update_to_dict(self):
        """Test converting price update to dictionary."""
        update = PriceUpdate(
            symbol="ETH",
            price=Decimal("3000.50"),
            source=DataSource.COINBASE
        )
        
        result = update.to_dict()
        
        assert result["symbol"] == "ETH"
        assert result["price"] == 3000.50
        assert result["source"] == "coinbase"
        assert "timestamp" in result
        assert result["volume_24h"] is None
        assert result["change_24h"] is None


class TestBasePriceFeed:
    """Test BasePriceFeed class."""
    
    def test_base_price_feed_creation(self):
        """Test creating a base price feed."""
        feed = BasePriceFeed(PriceFeedProvider.MOCK, ["BTC", "ETH"])
        
        assert feed.provider == PriceFeedProvider.MOCK
        assert feed.symbols == {"BTC", "ETH"}
        assert len(feed.handlers) == 0
        assert not feed._running
    
    async def test_start_stop(self):
        """Test starting and stopping the feed."""
        feed = BasePriceFeed(PriceFeedProvider.MOCK, ["BTC"])
        
        assert not feed._running
        
        await feed.start()
        assert feed._running
        
        await feed.stop()
        assert not feed._running
    
    def test_add_remove_handler(self):
        """Test adding and removing handlers."""
        feed = BasePriceFeed(PriceFeedProvider.MOCK, ["BTC"])
        handler = Mock()
        
        feed.add_handler(handler)
        assert handler in feed.handlers
        
        feed.remove_handler(handler)
        assert handler not in feed.handlers
    
    def test_add_remove_symbol(self):
        """Test adding and removing symbols."""
        feed = BasePriceFeed(PriceFeedProvider.MOCK, ["BTC"])
        
        assert "BTC" in feed.symbols
        assert "ETH" not in feed.symbols
        
        feed.add_symbol("ETH")
        assert "ETH" in feed.symbols
        
        feed.remove_symbol("BTC")
        assert "BTC" not in feed.symbols
    
    async def test_notify_handlers(self):
        """Test notifying handlers of price updates."""
        feed = BasePriceFeed(PriceFeedProvider.MOCK, ["BTC"])
        
        sync_handler = Mock()
        async_handler = AsyncMock()
        error_handler = Mock(side_effect=Exception("Handler error"))
        
        feed.add_handler(sync_handler)
        feed.add_handler(async_handler)
        feed.add_handler(error_handler)
        
        update = PriceUpdate(symbol="BTC", price=Decimal("50000"))
        
        # Should not raise exception even with error handler
        await feed._notify_handlers(update)
        
        sync_handler.assert_called_once_with(update)
        async_handler.assert_called_once_with(update)
        error_handler.assert_called_once_with(update)


@pytest.mark.asyncio
class TestMockPriceFeed:
    """Test MockPriceFeed class."""
    
    def test_mock_price_feed_creation(self):
        """Test creating a mock price feed."""
        feed = MockPriceFeed(["BTC", "ETH"])
        
        assert feed.provider == PriceFeedProvider.MOCK
        assert feed.symbols == {"BTC", "ETH"}
        assert "BTC" in feed._base_prices
        assert "ETH" in feed._base_prices
    
    async def test_mock_price_generation(self):
        """Test mock price generation."""
        feed = MockPriceFeed(["BTC"])
        handler = Mock()
        feed.add_handler(handler)
        
        await feed.start()
        
        # Wait a bit for price generation
        await asyncio.sleep(0.1)
        
        await feed.stop()
        
        # Should have generated at least one price update
        assert handler.call_count > 0
        
        # Check the update structure
        call_args = handler.call_args[0][0]
        assert isinstance(call_args, PriceUpdate)
        assert call_args.symbol == "BTC"
        assert call_args.source == DataSource.MOCK
    
    async def test_mock_price_variation(self):
        """Test that mock prices vary over time."""
        feed = MockPriceFeed(["BTC"])
        prices = []

        def price_handler(update):
            prices.append(float(update.price))

        feed.add_handler(price_handler)

        await feed.start()
        await asyncio.sleep(2.5)  # Wait for at least 2 price updates (updates every 1 second)
        await feed.stop()

        # Should have multiple different prices
        assert len(prices) > 1
        assert len(set(prices)) > 1  # Prices should be different


@pytest.mark.asyncio
class TestBinancePriceFeed:
    """Test BinancePriceFeed class."""
    
    def test_binance_price_feed_creation(self):
        """Test creating a Binance price feed."""
        feed = BinancePriceFeed(["BTC", "ETH"])
        
        assert feed.provider == PriceFeedProvider.BINANCE
        assert feed.symbols == {"BTC", "ETH"}
        assert feed.stream_manager is None
    
    @patch('crypto_portfolio_analyzer.streaming.price_feeds.StreamManager')
    async def test_binance_start(self, mock_stream_manager_class):
        """Test starting Binance price feed."""
        mock_manager = AsyncMock()
        mock_stream_manager_class.return_value = mock_manager
        
        feed = BinancePriceFeed(["BTC"])
        await feed.start()
        
        assert feed.stream_manager == mock_manager
        mock_manager.start.assert_called_once()
        mock_manager.add_stream.assert_called_once()
        mock_manager.add_global_handler.assert_called_once()
    
    async def test_binance_message_handling(self):
        """Test handling Binance WebSocket messages."""
        feed = BinancePriceFeed(["BTC"])
        handler = Mock()
        feed.add_handler(handler)
        
        # Simulate Binance ticker message
        binance_message = {
            "s": "BTCUSDT",  # Symbol
            "c": "50000.00",  # Close price
            "v": "1000000",   # Volume
            "P": "2.50"       # Price change percent
        }
        
        await feed._handle_binance_message("binance_btc", binance_message)
        
        handler.assert_called_once()
        update = handler.call_args[0][0]
        
        assert isinstance(update, PriceUpdate)
        assert update.symbol == "BTC"
        assert update.price == Decimal("50000.00")
        assert update.volume_24h == Decimal("1000000")
        assert update.change_percent_24h == 2.50
        assert update.source == DataSource.BINANCE
    
    async def test_binance_invalid_message(self):
        """Test handling invalid Binance messages."""
        feed = BinancePriceFeed(["BTC"])
        handler = Mock()
        feed.add_handler(handler)
        
        # Invalid message (missing required fields)
        invalid_message = {"invalid": "data"}
        
        # Should not raise exception or call handler
        await feed._handle_binance_message("binance_btc", invalid_message)
        handler.assert_not_called()


@pytest.mark.asyncio
class TestCoinbasePriceFeed:
    """Test CoinbasePriceFeed class."""
    
    def test_coinbase_price_feed_creation(self):
        """Test creating a Coinbase price feed."""
        feed = CoinbasePriceFeed(["BTC", "ETH"])
        
        assert feed.provider == PriceFeedProvider.COINBASE
        assert feed.symbols == {"BTC", "ETH"}
        assert feed.stream_manager is None
    
    async def test_coinbase_message_handling(self):
        """Test handling Coinbase WebSocket messages."""
        feed = CoinbasePriceFeed(["BTC"])
        handler = Mock()
        feed.add_handler(handler)
        
        # Simulate Coinbase ticker message
        coinbase_message = {
            "type": "ticker",
            "product_id": "BTC-USD",
            "price": "50000.00",
            "volume_24h": "1000000",
            "open_24h": "49000.00"
        }
        
        await feed._handle_coinbase_message("coinbase_feed", coinbase_message)
        
        handler.assert_called_once()
        update = handler.call_args[0][0]
        
        assert isinstance(update, PriceUpdate)
        assert update.symbol == "BTC"
        assert update.price == Decimal("50000.00")
        assert update.volume_24h == Decimal("1000000")
        assert update.source == DataSource.COINBASE
    
    async def test_coinbase_invalid_message(self):
        """Test handling invalid Coinbase messages."""
        feed = CoinbasePriceFeed(["BTC"])
        handler = Mock()
        feed.add_handler(handler)
        
        # Wrong message type
        invalid_message = {"type": "heartbeat"}
        
        # Should not call handler
        await feed._handle_coinbase_message("coinbase_feed", invalid_message)
        handler.assert_not_called()


@pytest.mark.asyncio
class TestPriceFeedManager:
    """Test PriceFeedManager class."""
    
    def test_price_feed_manager_creation(self):
        """Test creating a price feed manager."""
        manager = PriceFeedManager()
        
        assert len(manager.feeds) == 0
        assert manager.primary_provider is None
        assert len(manager.fallback_providers) == 0
        assert len(manager.symbols) == 0
        assert len(manager.handlers) == 0
        assert not manager._running
    
    def test_add_provider(self):
        """Test adding price feed providers."""
        manager = PriceFeedManager()
        
        # Add primary provider
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC", "ETH"], is_primary=True)
        
        assert PriceFeedProvider.MOCK in manager.feeds
        assert manager.primary_provider == PriceFeedProvider.MOCK
        assert "BTC" in manager.symbols
        assert "ETH" in manager.symbols
        
        # Add fallback provider
        manager.add_provider(PriceFeedProvider.BINANCE, ["BTC"], is_primary=False)
        
        assert PriceFeedProvider.BINANCE in manager.feeds
        assert PriceFeedProvider.BINANCE in manager.fallback_providers
    
    def test_add_unsupported_provider(self):
        """Test adding unsupported provider."""
        manager = PriceFeedManager()
        
        with pytest.raises(ValueError):
            manager.add_provider("unsupported", ["BTC"])
    
    def test_add_remove_handler(self):
        """Test adding and removing handlers."""
        manager = PriceFeedManager()
        handler = Mock()
        
        manager.add_handler(handler)
        assert handler in manager.handlers
        
        manager.remove_handler(handler)
        assert handler not in manager.handlers
    
    async def test_start_stop(self):
        """Test starting and stopping the manager."""
        manager = PriceFeedManager()
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC"], is_primary=True)
        
        assert not manager._running
        
        await manager.start()
        assert manager._running
        
        # Primary provider should be started
        primary_feed = manager.feeds[PriceFeedProvider.MOCK]
        assert primary_feed._running
        
        await manager.stop()
        assert not manager._running
        assert not primary_feed._running
    
    async def test_price_update_handling(self):
        """Test handling price updates from feeds."""
        manager = PriceFeedManager()
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC"], is_primary=True)
        
        handler = Mock()
        manager.add_handler(handler)
        
        # Simulate price update
        update = PriceUpdate(symbol="BTC", price=Decimal("50000"))
        await manager._handle_price_update(update)
        
        # Should update last seen time
        assert "BTC" in manager._last_update_times
        
        # Should call handler
        handler.assert_called_once_with(update)
    
    def test_get_last_update_time(self):
        """Test getting last update time for symbols."""
        manager = PriceFeedManager()
        
        # Non-existent symbol
        assert manager.get_last_update_time("BTC") is None
        
        # Add update time
        now = datetime.now(timezone.utc)
        manager._last_update_times["BTC"] = now
        
        assert manager.get_last_update_time("BTC") == now
    
    def test_get_provider_status(self):
        """Test getting provider status."""
        manager = PriceFeedManager()
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC"], is_primary=True)
        
        status = manager.get_provider_status()
        
        assert "mock" in status
        assert "running" in status["mock"]
        assert "symbols" in status["mock"]
        assert "handler_count" in status["mock"]


@pytest.mark.asyncio
class TestPriceFeedIntegration:
    """Integration tests for price feeds."""
    
    async def test_manager_with_multiple_providers(self):
        """Test manager with multiple providers."""
        manager = PriceFeedManager()
        
        # Add multiple providers
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC"], is_primary=True)
        manager.add_provider(PriceFeedProvider.BINANCE, ["ETH"], is_primary=False)
        
        assert len(manager.feeds) == 2
        assert manager.primary_provider == PriceFeedProvider.MOCK
        assert PriceFeedProvider.BINANCE in manager.fallback_providers
        
        # Test that all symbols are tracked
        assert "BTC" in manager.symbols
        assert "ETH" in manager.symbols
    
    async def test_end_to_end_mock_feed(self):
        """Test end-to-end with mock feed."""
        manager = PriceFeedManager()
        manager.add_provider(PriceFeedProvider.MOCK, ["BTC"], is_primary=True)
        
        updates = []
        
        def update_handler(update):
            updates.append(update)
        
        manager.add_handler(update_handler)
        
        await manager.start()
        await asyncio.sleep(0.1)  # Let it generate some updates
        await manager.stop()
        
        # Should have received updates
        assert len(updates) > 0
        
        # Check update structure
        update = updates[0]
        assert isinstance(update, PriceUpdate)
        assert update.symbol == "BTC"
        assert update.source == DataSource.MOCK

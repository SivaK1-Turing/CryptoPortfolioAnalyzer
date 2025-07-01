"""Tests for cryptocurrency data models."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.data.models import (
    CryptocurrencyPrice,
    HistoricalPrice,
    MarketData,
    CacheEntry,
    APIResponse,
    DataSource,
    PriceChangeInterval
)


class TestCryptocurrencyPrice:
    """Test CryptocurrencyPrice model."""
    
    def test_cryptocurrency_price_creation(self):
        """Test creating a CryptocurrencyPrice instance."""
        price = CryptocurrencyPrice(
            symbol="BTC",
            name="Bitcoin",
            current_price=Decimal("50000.00"),
            currency="usd",
            market_cap=Decimal("1000000000000"),
            volume_24h=Decimal("50000000000"),
            price_change_percentage_24h=2.5
        )
        
        assert price.symbol == "BTC"
        assert price.name == "Bitcoin"
        assert price.current_price == Decimal("50000.00")
        assert price.currency == "usd"
        assert price.market_cap == Decimal("1000000000000")
        assert price.volume_24h == Decimal("50000000000")
        assert price.price_change_percentage_24h == 2.5
        assert price.data_source == DataSource.COINGECKO
        assert isinstance(price.last_updated, datetime)
    
    def test_cryptocurrency_price_post_init(self):
        """Test post-initialization processing."""
        price = CryptocurrencyPrice(
            symbol="btc",  # lowercase
            name="Bitcoin",
            current_price=50000.0  # float
        )
        
        # Symbol should be uppercase
        assert price.symbol == "BTC"
        
        # Price should be converted to Decimal
        assert isinstance(price.current_price, Decimal)
        assert price.current_price == Decimal("50000.0")
        
        # Timezone should be set
        assert price.last_updated.tzinfo is not None
    
    def test_cryptocurrency_price_to_dict(self):
        """Test converting CryptocurrencyPrice to dictionary."""
        now = datetime.now(timezone.utc)
        price = CryptocurrencyPrice(
            symbol="ETH",
            name="Ethereum",
            current_price=Decimal("3000.00"),
            last_updated=now
        )
        
        price_dict = price.to_dict()
        
        assert price_dict["symbol"] == "ETH"
        assert price_dict["name"] == "Ethereum"
        assert price_dict["current_price"] == 3000.0
        assert price_dict["last_updated"] == now.isoformat()
        assert price_dict["data_source"] == "coingecko"
    
    def test_cryptocurrency_price_from_dict(self):
        """Test creating CryptocurrencyPrice from dictionary."""
        now = datetime.now(timezone.utc)
        price_dict = {
            "symbol": "ADA",
            "name": "Cardano",
            "current_price": 1.5,
            "currency": "usd",
            "last_updated": now.isoformat(),
            "data_source": "coingecko"
        }
        
        price = CryptocurrencyPrice.from_dict(price_dict)
        
        assert price.symbol == "ADA"
        assert price.name == "Cardano"
        assert price.current_price == Decimal("1.5")
        assert price.currency == "usd"
        assert price.last_updated == now
        assert price.data_source == DataSource.COINGECKO
    
    def test_price_change_percentage_1h_property(self):
        """Test 1-hour price change percentage property."""
        price = CryptocurrencyPrice(
            symbol="BTC",
            name="Bitcoin",
            current_price=Decimal("50000.00")
        )
        
        # Initially None
        assert price.price_change_percentage_1h is None
        
        # Set value
        price.price_change_percentage_1h = 1.5
        assert price.price_change_percentage_1h == 1.5


class TestHistoricalPrice:
    """Test HistoricalPrice model."""
    
    def test_historical_price_creation(self):
        """Test creating a HistoricalPrice instance."""
        timestamp = datetime.now(timezone.utc)
        price = HistoricalPrice(
            symbol="BTC",
            timestamp=timestamp,
            price=Decimal("45000.00"),
            currency="usd",
            volume=Decimal("1000000000"),
            data_source=DataSource.COINGECKO
        )
        
        assert price.symbol == "BTC"
        assert price.timestamp == timestamp
        assert price.price == Decimal("45000.00")
        assert price.currency == "usd"
        assert price.volume == Decimal("1000000000")
        assert price.data_source == DataSource.COINGECKO
    
    def test_historical_price_post_init(self):
        """Test post-initialization processing."""
        timestamp = datetime.now()  # No timezone
        price = HistoricalPrice(
            symbol="eth",  # lowercase
            timestamp=timestamp,
            price=3000.0  # float
        )
        
        # Symbol should be uppercase
        assert price.symbol == "ETH"
        
        # Price should be converted to Decimal
        assert isinstance(price.price, Decimal)
        assert price.price == Decimal("3000.0")
        
        # Timezone should be set
        assert price.timestamp.tzinfo is not None


class TestMarketData:
    """Test MarketData model."""
    
    def test_market_data_creation(self):
        """Test creating a MarketData instance."""
        current_price = CryptocurrencyPrice(
            symbol="BTC",
            name="Bitcoin",
            current_price=Decimal("50000.00")
        )
        
        market_data = MarketData(
            symbol="BTC",
            name="Bitcoin",
            current_price=current_price
        )
        
        assert market_data.symbol == "BTC"
        assert market_data.name == "Bitcoin"
        assert market_data.current_price == current_price
        assert isinstance(market_data.price_changes, dict)
        assert isinstance(market_data.historical_prices, list)
        assert isinstance(market_data.last_updated, datetime)
    
    def test_market_data_price_changes(self):
        """Test price change management."""
        current_price = CryptocurrencyPrice(
            symbol="ETH",
            name="Ethereum",
            current_price=Decimal("3000.00")
        )
        
        market_data = MarketData(
            symbol="ETH",
            name="Ethereum",
            current_price=current_price
        )
        
        # Add price changes
        market_data.add_price_change(PriceChangeInterval.HOUR_24, 5.2)
        market_data.add_price_change(PriceChangeInterval.DAYS_7, -2.1)
        
        # Get price changes
        assert market_data.get_price_change(PriceChangeInterval.HOUR_24) == 5.2
        assert market_data.get_price_change(PriceChangeInterval.DAYS_7) == -2.1
        assert market_data.get_price_change(PriceChangeInterval.DAYS_30) is None


class TestCacheEntry:
    """Test CacheEntry model."""
    
    def test_cache_entry_creation(self):
        """Test creating a CacheEntry instance."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"}
        )
        
        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert isinstance(entry.created_at, datetime)
        assert entry.expires_at is None
        assert entry.access_count == 0
        assert isinstance(entry.last_accessed, datetime)
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration logic."""
        # Non-expiring entry
        entry = CacheEntry(key="test", value="data")
        assert not entry.is_expired
        
        # Expired entry
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        entry_expired = CacheEntry(
            key="test",
            value="data",
            expires_at=past_time
        )
        assert entry_expired.is_expired
        
        # Future expiration
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        entry_future = CacheEntry(
            key="test",
            value="data",
            expires_at=future_time
        )
        assert not entry_future.is_expired
    
    def test_cache_entry_access(self):
        """Test cache entry access tracking."""
        entry = CacheEntry(key="test", value="data")
        
        initial_count = entry.access_count
        initial_time = entry.last_accessed
        
        # Access the entry
        entry.access()
        
        assert entry.access_count == initial_count + 1
        assert entry.last_accessed > initial_time


class TestAPIResponse:
    """Test APIResponse model."""
    
    def test_api_response_creation(self):
        """Test creating an APIResponse instance."""
        response = APIResponse(
            data={"price": 50000},
            status_code=200,
            headers={"Content-Type": "application/json"},
            response_time=0.5,
            data_source=DataSource.COINGECKO
        )
        
        assert response.data == {"price": 50000}
        assert response.status_code == 200
        assert response.headers == {"Content-Type": "application/json"}
        assert response.response_time == 0.5
        assert response.data_source == DataSource.COINGECKO
        assert isinstance(response.timestamp, datetime)
        assert not response.cached
    
    def test_api_response_is_success(self):
        """Test success status checking."""
        # Successful responses
        assert APIResponse(data={}, status_code=200).is_success
        assert APIResponse(data={}, status_code=201).is_success
        assert APIResponse(data={}, status_code=299).is_success
        
        # Failed responses
        assert not APIResponse(data={}, status_code=400).is_success
        assert not APIResponse(data={}, status_code=404).is_success
        assert not APIResponse(data={}, status_code=500).is_success
    
    def test_api_response_to_json(self):
        """Test JSON serialization."""
        response = APIResponse(
            data={"symbol": "BTC", "price": 50000},
            status_code=200
        )
        
        json_str = response.to_json()
        assert '"symbol": "BTC"' in json_str
        assert '"price": 50000' in json_str


class TestEnums:
    """Test enum classes."""
    
    def test_data_source_enum(self):
        """Test DataSource enum."""
        assert DataSource.COINGECKO.value == "coingecko"
        assert DataSource.COINMARKETCAP.value == "coinmarketcap"
        assert DataSource.BINANCE.value == "binance"
        assert DataSource.MANUAL.value == "manual"
    
    def test_price_change_interval_enum(self):
        """Test PriceChangeInterval enum."""
        assert PriceChangeInterval.HOUR_1.value == "1h"
        assert PriceChangeInterval.HOUR_24.value == "24h"
        assert PriceChangeInterval.DAYS_7.value == "7d"
        assert PriceChangeInterval.DAYS_30.value == "30d"
        assert PriceChangeInterval.DAYS_90.value == "90d"
        assert PriceChangeInterval.YEAR_1.value == "1y"

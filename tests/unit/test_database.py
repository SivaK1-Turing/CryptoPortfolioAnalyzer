"""Tests for database manager."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.data.database import DatabaseManager
from crypto_portfolio_analyzer.data.models import CryptocurrencyPrice, HistoricalPrice, DataSource


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = Path(tmp.name)
    
    db_manager = DatabaseManager(db_path)
    await db_manager.initialize()
    
    yield db_manager
    
    await db_manager.close()
    
    # Clean up
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_current_price():
    """Create a sample CryptocurrencyPrice for testing."""
    return CryptocurrencyPrice(
        symbol="BTC",
        name="Bitcoin",
        current_price=Decimal("50000.00"),
        currency="usd",
        market_cap=Decimal("1000000000000"),
        volume_24h=Decimal("50000000000"),
        price_change_24h=Decimal("1000.00"),
        price_change_percentage_24h=2.5,
        circulating_supply=Decimal("19000000"),
        total_supply=Decimal("21000000"),
        max_supply=Decimal("21000000"),
        ath=Decimal("69000.00"),
        ath_date=datetime(2021, 11, 10, tzinfo=timezone.utc),
        atl=Decimal("3200.00"),
        atl_date=datetime(2020, 3, 13, tzinfo=timezone.utc),
        last_updated=datetime.now(timezone.utc),
        data_source=DataSource.COINGECKO
    )


@pytest.fixture
def sample_historical_prices():
    """Create sample HistoricalPrice instances for testing."""
    base_time = datetime.now(timezone.utc) - timedelta(days=7)
    prices = []
    
    for i in range(7):
        timestamp = base_time + timedelta(days=i)
        price = HistoricalPrice(
            symbol="ETH",
            timestamp=timestamp,
            price=Decimal(f"{3000 + i * 100}.00"),
            currency="usd",
            volume=Decimal(f"{1000000000 + i * 100000000}"),
            market_cap=Decimal(f"{400000000000 + i * 10000000000}"),
            data_source=DataSource.COINGECKO
        )
        prices.append(price)
    
    return prices


class TestDatabaseManager:
    """Test DatabaseManager functionality."""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db):
        """Test database initialization and table creation."""
        db_manager = temp_db
        
        # Database should be initialized
        assert db_manager._initialized
        assert db_manager.db_path.exists()
    
    @pytest.mark.asyncio
    async def test_save_current_price(self, temp_db, sample_current_price):
        """Test saving current price data."""
        db_manager = temp_db
        
        # Save price
        success = await db_manager.save_current_price(sample_current_price)
        assert success
        
        # Retrieve and verify
        retrieved_price = await db_manager.get_current_price("BTC", "usd")
        assert retrieved_price is not None
        assert retrieved_price.symbol == "BTC"
        assert retrieved_price.name == "Bitcoin"
        assert retrieved_price.current_price == Decimal("50000.00")
        assert retrieved_price.currency == "usd"
        assert retrieved_price.market_cap == Decimal("1000000000000")
        assert retrieved_price.volume_24h == Decimal("50000000000")
        assert retrieved_price.price_change_percentage_24h == 2.5
        assert retrieved_price.data_source == DataSource.COINGECKO
    
    @pytest.mark.asyncio
    async def test_save_current_price_upsert(self, temp_db, sample_current_price):
        """Test that saving the same price updates existing record."""
        db_manager = temp_db
        
        # Save initial price
        await db_manager.save_current_price(sample_current_price)
        
        # Update price
        sample_current_price.current_price = Decimal("55000.00")
        sample_current_price.price_change_percentage_24h = 10.0
        
        # Save updated price
        success = await db_manager.save_current_price(sample_current_price)
        assert success
        
        # Retrieve and verify update
        retrieved_price = await db_manager.get_current_price("BTC", "usd")
        assert retrieved_price.current_price == Decimal("55000.00")
        assert retrieved_price.price_change_percentage_24h == 10.0
    
    @pytest.mark.asyncio
    async def test_get_current_price_not_found(self, temp_db):
        """Test getting current price for non-existent symbol."""
        db_manager = temp_db
        
        price = await db_manager.get_current_price("NONEXISTENT", "usd")
        assert price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_with_data_source(self, temp_db, sample_current_price):
        """Test getting current price filtered by data source."""
        db_manager = temp_db
        
        # Save price with CoinGecko source
        await db_manager.save_current_price(sample_current_price)
        
        # Should find with correct source
        price = await db_manager.get_current_price("BTC", "usd", DataSource.COINGECKO)
        assert price is not None
        assert price.data_source == DataSource.COINGECKO
        
        # Should not find with different source
        price = await db_manager.get_current_price("BTC", "usd", DataSource.COINMARKETCAP)
        assert price is None
    
    @pytest.mark.asyncio
    async def test_save_historical_prices(self, temp_db, sample_historical_prices):
        """Test saving historical price data."""
        db_manager = temp_db
        
        # Save historical prices
        saved_count = await db_manager.save_historical_prices(sample_historical_prices)
        assert saved_count == len(sample_historical_prices)
    
    @pytest.mark.asyncio
    async def test_save_historical_prices_empty_list(self, temp_db):
        """Test saving empty list of historical prices."""
        db_manager = temp_db
        
        saved_count = await db_manager.save_historical_prices([])
        assert saved_count == 0
    
    @pytest.mark.asyncio
    async def test_get_historical_prices(self, temp_db, sample_historical_prices):
        """Test retrieving historical price data."""
        db_manager = temp_db
        
        # Save historical prices
        await db_manager.save_historical_prices(sample_historical_prices)
        
        # Define date range
        start_date = sample_historical_prices[0].timestamp
        end_date = sample_historical_prices[-1].timestamp
        
        # Retrieve historical prices
        retrieved_prices = await db_manager.get_historical_prices(
            "ETH", start_date, end_date, "usd"
        )
        
        assert len(retrieved_prices) == len(sample_historical_prices)
        
        # Verify first and last prices
        assert retrieved_prices[0].symbol == "ETH"
        assert retrieved_prices[0].price == Decimal("3000.00")
        assert retrieved_prices[-1].price == Decimal("3600.00")
        
        # Verify ordering (should be ascending by timestamp)
        for i in range(1, len(retrieved_prices)):
            assert retrieved_prices[i].timestamp >= retrieved_prices[i-1].timestamp
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_date_range(self, temp_db, sample_historical_prices):
        """Test retrieving historical prices within specific date range."""
        db_manager = temp_db
        
        # Save historical prices
        await db_manager.save_historical_prices(sample_historical_prices)
        
        # Get subset of data (middle 3 days)
        start_date = sample_historical_prices[2].timestamp
        end_date = sample_historical_prices[4].timestamp
        
        retrieved_prices = await db_manager.get_historical_prices(
            "ETH", start_date, end_date, "usd"
        )
        
        # Should get 3 records
        assert len(retrieved_prices) == 3
        assert all(start_date <= p.timestamp <= end_date for p in retrieved_prices)
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_not_found(self, temp_db):
        """Test getting historical prices for non-existent symbol."""
        db_manager = temp_db
        
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        prices = await db_manager.get_historical_prices(
            "NONEXISTENT", start_date, end_date, "usd"
        )
        assert prices == []
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, temp_db, sample_current_price, sample_historical_prices):
        """Test cleaning up old data."""
        db_manager = temp_db
        
        # Save current and historical data
        await db_manager.save_current_price(sample_current_price)
        await db_manager.save_historical_prices(sample_historical_prices)
        
        # Create old historical data
        old_time = datetime.now(timezone.utc) - timedelta(days=400)
        old_price = HistoricalPrice(
            symbol="OLD",
            timestamp=old_time,
            price=Decimal("1000.00"),
            currency="usd",
            data_source=DataSource.COINGECKO
        )
        await db_manager.save_historical_prices([old_price])
        
        # Cleanup data older than 365 days
        deleted_count = await db_manager.cleanup_old_data(365)
        
        # Should have deleted the old record
        assert deleted_count >= 1
        
        # Verify old data is gone
        very_old_start = datetime.now(timezone.utc) - timedelta(days=500)
        very_old_end = datetime.now(timezone.utc) - timedelta(days=300)
        old_prices = await db_manager.get_historical_prices(
            "OLD", very_old_start, very_old_end, "usd"
        )
        assert len(old_prices) == 0
        
        # Verify recent data is still there
        recent_prices = await db_manager.get_historical_prices(
            "ETH", 
            datetime.now(timezone.utc) - timedelta(days=10),
            datetime.now(timezone.utc),
            "usd"
        )
        assert len(recent_prices) > 0
    
    @pytest.mark.asyncio
    async def test_row_to_current_price_conversion(self, temp_db, sample_current_price):
        """Test internal row to CryptocurrencyPrice conversion."""
        db_manager = temp_db
        
        # Save and retrieve price to test conversion
        await db_manager.save_current_price(sample_current_price)
        retrieved_price = await db_manager.get_current_price("BTC", "usd")
        
        # Verify all fields are correctly converted
        assert isinstance(retrieved_price.current_price, Decimal)
        assert isinstance(retrieved_price.market_cap, Decimal)
        assert isinstance(retrieved_price.volume_24h, Decimal)
        assert isinstance(retrieved_price.last_updated, datetime)
        assert isinstance(retrieved_price.data_source, DataSource)
        
        # Verify optional datetime fields
        if retrieved_price.ath_date:
            assert isinstance(retrieved_price.ath_date, datetime)
        if retrieved_price.atl_date:
            assert isinstance(retrieved_price.atl_date, datetime)
    
    @pytest.mark.asyncio
    async def test_row_to_historical_price_conversion(self, temp_db, sample_historical_prices):
        """Test internal row to HistoricalPrice conversion."""
        db_manager = temp_db
        
        # Save and retrieve historical prices to test conversion
        await db_manager.save_historical_prices(sample_historical_prices[:1])
        
        start_date = sample_historical_prices[0].timestamp - timedelta(hours=1)
        end_date = sample_historical_prices[0].timestamp + timedelta(hours=1)
        
        retrieved_prices = await db_manager.get_historical_prices(
            "ETH", start_date, end_date, "usd"
        )
        
        assert len(retrieved_prices) == 1
        price = retrieved_prices[0]
        
        # Verify all fields are correctly converted
        assert isinstance(price.price, Decimal)
        assert isinstance(price.timestamp, datetime)
        assert isinstance(price.data_source, DataSource)
        
        # Verify optional fields
        if price.volume:
            assert isinstance(price.volume, Decimal)
        if price.market_cap:
            assert isinstance(price.market_cap, Decimal)
    
    @pytest.mark.asyncio
    async def test_database_close(self, temp_db):
        """Test database connection cleanup."""
        db_manager = temp_db
        
        # Close should not raise any errors
        await db_manager.close()
        
        # Should be able to call close multiple times
        await db_manager.close()

    @pytest.mark.asyncio
    async def test_database_error_handling(self, temp_db):
        """Test database error handling."""
        db_manager = temp_db

        # Test with invalid price data
        invalid_price = CryptocurrencyPrice(
            symbol="TEST",
            name="Test",
            current_price=Decimal("50000.00")
        )

        # This should still work as the model handles defaults
        success = await db_manager.save_current_price(invalid_price)
        assert success

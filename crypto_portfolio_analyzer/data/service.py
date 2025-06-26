"""Data aggregation service for cryptocurrency market data."""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
import logging

from .models import CryptocurrencyPrice, HistoricalPrice, DataSource
from .database import DatabaseManager
from .cache import CacheManager, cache_key_for_price, cache_key_for_historical
from .api_client import APIClientManager
from .clients.coingecko import CoinGeckoClient

logger = logging.getLogger(__name__)


class DataService:
    """Service for aggregating cryptocurrency data from multiple sources."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None,
                 cache_manager: Optional[CacheManager] = None,
                 client_manager: Optional[APIClientManager] = None):
        """Initialize data service.
        
        Args:
            db_manager: Database manager for persistence
            cache_manager: Cache manager for temporary storage
            client_manager: API client manager for data fetching
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.client_manager = client_manager
        self._initialized = False
    
    async def initialize(self):
        """Initialize the data service and all components."""
        if self._initialized:
            return
        
        # Initialize database
        if self.db_manager:
            await self.db_manager.initialize()
        
        # Initialize cache
        if self.cache_manager:
            await self.cache_manager.start()
        
        # Initialize API clients
        if self.client_manager:
            await self.client_manager.start_all()
        
        self._initialized = True
        logger.info("Data service initialized")
    
    async def shutdown(self):
        """Shutdown the data service and cleanup resources."""
        if not self._initialized:
            return
        
        # Shutdown components
        if self.cache_manager:
            await self.cache_manager.stop()
        
        if self.client_manager:
            await self.client_manager.stop_all()
        
        if self.db_manager:
            await self.db_manager.close()
        
        self._initialized = False
        logger.info("Data service shutdown")
    
    async def get_current_price(self, symbol: str, currency: str = "usd", 
                              use_cache: bool = True, cache_ttl: int = 300) -> Optional[CryptocurrencyPrice]:
        """Get current price for a cryptocurrency.
        
        Args:
            symbol: Cryptocurrency symbol
            currency: Target currency
            use_cache: Whether to use cached data
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            CryptocurrencyPrice instance or None if not found
        """
        symbol = symbol.upper()
        cache_key = await cache_key_for_price(symbol, currency)
        
        # Try cache first if enabled
        if use_cache and self.cache_manager:
            cached_price = await self.cache_manager.get(cache_key)
            if cached_price:
                logger.debug(f"Cache hit for {symbol} price")
                return CryptocurrencyPrice.from_dict(cached_price)
        
        # Try API clients
        if self.client_manager:
            price = await self.client_manager.get_current_price(symbol, currency)
            if price:
                # Cache the result
                if use_cache and self.cache_manager:
                    await self.cache_manager.set(cache_key, price.to_dict(), cache_ttl)
                
                # Save to database
                if self.db_manager:
                    await self.db_manager.save_current_price(price)
                
                return price
        
        # Try database as fallback
        if self.db_manager:
            price = await self.db_manager.get_current_price(symbol, currency)
            if price:
                # Check if data is recent enough (within 1 hour)
                age = datetime.now(timezone.utc) - price.last_updated
                if age.total_seconds() < 3600:  # 1 hour
                    logger.info(f"Using database fallback for {symbol} (age: {age})")
                    return price
        
        logger.warning(f"Could not get current price for {symbol}")
        return None
    
    async def get_multiple_prices(self, symbols: List[str], currency: str = "usd",
                                use_cache: bool = True, cache_ttl: int = 300) -> List[CryptocurrencyPrice]:
        """Get current prices for multiple cryptocurrencies.
        
        Args:
            symbols: List of cryptocurrency symbols
            currency: Target currency
            use_cache: Whether to use cached data
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            List of CryptocurrencyPrice instances
        """
        if not symbols:
            return []
        
        symbols = [s.upper() for s in symbols]
        prices = []
        uncached_symbols = []
        
        # Check cache for each symbol
        if use_cache and self.cache_manager:
            for symbol in symbols:
                cache_key = await cache_key_for_price(symbol, currency)
                cached_price = await self.cache_manager.get(cache_key)
                
                if cached_price:
                    prices.append(CryptocurrencyPrice.from_dict(cached_price))
                    logger.debug(f"Cache hit for {symbol} price")
                else:
                    uncached_symbols.append(symbol)
        else:
            uncached_symbols = symbols
        
        # Fetch uncached symbols from API
        if uncached_symbols and self.client_manager:
            api_prices = await self.client_manager.get_multiple_prices(uncached_symbols, currency)
            
            for price in api_prices:
                prices.append(price)
                
                # Cache the result
                if use_cache and self.cache_manager:
                    cache_key = await cache_key_for_price(price.symbol, currency)
                    await self.cache_manager.set(cache_key, price.to_dict(), cache_ttl)
                
                # Save to database
                if self.db_manager:
                    await self.db_manager.save_current_price(price)
        
        return prices
    
    async def get_historical_prices(self, symbol: str, start_date: datetime, 
                                  end_date: datetime, currency: str = "usd",
                                  use_cache: bool = True, cache_ttl: int = 3600) -> List[HistoricalPrice]:
        """Get historical prices for a cryptocurrency.
        
        Args:
            symbol: Cryptocurrency symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            currency: Target currency
            use_cache: Whether to use cached data
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            List of HistoricalPrice instances
        """
        symbol = symbol.upper()
        cache_key = await cache_key_for_historical(symbol, start_date, end_date, currency)
        
        # Try cache first if enabled
        if use_cache and self.cache_manager:
            cached_prices = await self.cache_manager.get(cache_key)
            if cached_prices:
                logger.debug(f"Cache hit for {symbol} historical data")
                return [HistoricalPrice(**price_data) for price_data in cached_prices]
        
        # Try database first for historical data
        if self.db_manager:
            db_prices = await self.db_manager.get_historical_prices(symbol, start_date, end_date, currency)
            
            # Check if we have sufficient data coverage
            if db_prices:
                db_start = min(p.timestamp for p in db_prices)
                db_end = max(p.timestamp for p in db_prices)
                
                # If database covers the requested range, use it
                if db_start <= start_date and db_end >= end_date:
                    logger.debug(f"Using database historical data for {symbol}")
                    
                    # Cache the result
                    if use_cache and self.cache_manager:
                        price_dicts = [price.__dict__ for price in db_prices]
                        await self.cache_manager.set(cache_key, price_dicts, cache_ttl)
                    
                    return db_prices
        
        # Fetch from API if not in database or insufficient coverage
        if self.client_manager:
            # Try to get a client (preferably CoinGecko)
            client = self.client_manager.get_client(DataSource.COINGECKO)
            if client:
                api_prices = await client.get_historical_prices(symbol, start_date, end_date, currency)
                
                if api_prices:
                    # Save to database
                    if self.db_manager:
                        saved_count = await self.db_manager.save_historical_prices(api_prices)
                        logger.info(f"Saved {saved_count} historical prices for {symbol}")
                    
                    # Cache the result
                    if use_cache and self.cache_manager:
                        price_dicts = [price.__dict__ for price in api_prices]
                        await self.cache_manager.set(cache_key, price_dicts, cache_ttl)
                    
                    return api_prices
        
        logger.warning(f"Could not get historical prices for {symbol}")
        return []
    
    async def refresh_price_data(self, symbols: List[str], currency: str = "usd") -> Dict[str, bool]:
        """Refresh price data for multiple symbols.
        
        Args:
            symbols: List of cryptocurrency symbols to refresh
            currency: Target currency
            
        Returns:
            Dictionary mapping symbols to success status
        """
        results = {}
        
        if not symbols:
            return results
        
        # Invalidate cache for these symbols
        if self.cache_manager:
            for symbol in symbols:
                cache_key = await cache_key_for_price(symbol.upper(), currency)
                await self.cache_manager.delete(cache_key)
        
        # Fetch fresh data
        prices = await self.get_multiple_prices(symbols, currency, use_cache=False)
        
        # Map results
        fetched_symbols = {price.symbol for price in prices}
        for symbol in symbols:
            results[symbol.upper()] = symbol.upper() in fetched_symbols
        
        return results
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if self.cache_manager:
            return await self.cache_manager.get_stats()
        return {}
    
    async def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries.
        
        Args:
            pattern: Optional pattern to match (supports * wildcard)
            
        Returns:
            Number of entries cleared
        """
        if not self.cache_manager:
            return 0
        
        if pattern:
            return await self.cache_manager.invalidate_pattern(pattern)
        else:
            return await self.cache_manager.clear()
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> int:
        """Clean up old data from database.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Number of records deleted
        """
        if self.db_manager:
            return await self.db_manager.cleanup_old_data(days_to_keep)
        return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all components.
        
        Returns:
            Dictionary with health status of each component
        """
        health = {
            'database': False,
            'cache': False,
            'api_clients': {}
        }
        
        # Check database
        if self.db_manager:
            try:
                # Try a simple database operation
                await self.db_manager.get_current_price("BTC", "usd")
                health['database'] = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
        
        # Check cache
        if self.cache_manager:
            try:
                # Try a simple cache operation
                await self.cache_manager.set("health_check", "ok", 1)
                health['cache'] = await self.cache_manager.exists("health_check")
                await self.cache_manager.delete("health_check")
            except Exception as e:
                logger.error(f"Cache health check failed: {e}")
        
        # Check API clients
        if self.client_manager:
            for source in [DataSource.COINGECKO]:
                client = self.client_manager.get_client(source)
                if client:
                    health['api_clients'][source.value] = await client.health_check()
        
        return health


# Global data service instance
_global_data_service: Optional[DataService] = None


async def get_data_service() -> DataService:
    """Get global data service instance."""
    global _global_data_service
    
    if _global_data_service is None:
        # Initialize with default components
        from .database import DatabaseManager
        from .cache import CacheManager
        from .api_client import APIClientManager
        
        db_manager = DatabaseManager()
        cache_manager = CacheManager()
        client_manager = APIClientManager()
        
        # Register CoinGecko client as primary
        coingecko_client = CoinGeckoClient()
        client_manager.register_client(coingecko_client, is_primary=True)
        
        _global_data_service = DataService(db_manager, cache_manager, client_manager)
        await _global_data_service.initialize()
    
    return _global_data_service

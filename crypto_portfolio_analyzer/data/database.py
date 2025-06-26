"""Database management for cryptocurrency data storage."""

import sqlite3
import asyncio
import aiosqlite
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import logging

from .models import CryptocurrencyPrice, HistoricalPrice, DataSource

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for cryptocurrency data."""
    
    def __init__(self, db_path: Union[str, Path] = "crypto_data.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection_pool = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize database and create tables."""
        if self._initialized:
            return
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await db.commit()
        
        self._initialized = True
        logger.info(f"Database initialized at {self.db_path}")
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create database tables."""
        
        # Current prices table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS current_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                current_price DECIMAL(20,8) NOT NULL,
                currency TEXT DEFAULT 'usd',
                market_cap DECIMAL(20,2),
                volume_24h DECIMAL(20,2),
                price_change_24h DECIMAL(20,8),
                price_change_percentage_24h REAL,
                price_change_percentage_1h REAL,
                circulating_supply DECIMAL(20,2),
                total_supply DECIMAL(20,2),
                max_supply DECIMAL(20,2),
                ath DECIMAL(20,8),
                ath_date TIMESTAMP,
                atl DECIMAL(20,8),
                atl_date TIMESTAMP,
                last_updated TIMESTAMP NOT NULL,
                data_source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, currency, data_source)
            )
        """)
        
        # Historical prices table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                price DECIMAL(20,8) NOT NULL,
                currency TEXT DEFAULT 'usd',
                volume DECIMAL(20,2),
                market_cap DECIMAL(20,2),
                data_source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp, currency, data_source)
            )
        """)
        
        # Cache table for API responses
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # API rate limiting table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_source TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP NOT NULL,
                window_duration INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(data_source, endpoint, window_start)
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection):
        """Create database indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_current_prices_symbol ON current_prices(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_current_prices_last_updated ON current_prices(last_updated)",
            "CREATE INDEX IF NOT EXISTS idx_historical_prices_symbol ON historical_prices(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_historical_prices_timestamp ON historical_prices(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_historical_prices_symbol_timestamp ON historical_prices(symbol, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_key ON cache_entries(cache_key)",
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_expires ON cache_entries(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_api_rate_limits_source ON api_rate_limits(data_source, endpoint)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    async def save_current_price(self, price: CryptocurrencyPrice) -> bool:
        """Save current price data to database.
        
        Args:
            price: CryptocurrencyPrice instance to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO current_prices (
                        symbol, name, current_price, currency, market_cap, volume_24h,
                        price_change_24h, price_change_percentage_24h, price_change_percentage_1h,
                        circulating_supply, total_supply, max_supply, ath, ath_date,
                        atl, atl_date, last_updated, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    price.symbol, price.name, float(price.current_price), price.currency,
                    float(price.market_cap) if price.market_cap else None,
                    float(price.volume_24h) if price.volume_24h else None,
                    float(price.price_change_24h) if price.price_change_24h else None,
                    price.price_change_percentage_24h,
                    price.price_change_percentage_1h,
                    float(price.circulating_supply) if price.circulating_supply else None,
                    float(price.total_supply) if price.total_supply else None,
                    float(price.max_supply) if price.max_supply else None,
                    float(price.ath) if price.ath else None,
                    price.ath_date.isoformat() if price.ath_date else None,
                    float(price.atl) if price.atl else None,
                    price.atl_date.isoformat() if price.atl_date else None,
                    price.last_updated.isoformat(),
                    price.data_source.value
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save current price for {price.symbol}: {e}")
            return False
    
    async def get_current_price(self, symbol: str, currency: str = "usd", 
                              data_source: Optional[DataSource] = None) -> Optional[CryptocurrencyPrice]:
        """Get current price for a symbol.
        
        Args:
            symbol: Cryptocurrency symbol
            currency: Price currency (default: usd)
            data_source: Specific data source to query
            
        Returns:
            CryptocurrencyPrice instance or None if not found
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                query = """
                    SELECT * FROM current_prices 
                    WHERE symbol = ? AND currency = ?
                """
                params = [symbol.upper(), currency]
                
                if data_source:
                    query += " AND data_source = ?"
                    params.append(data_source.value)
                
                query += " ORDER BY last_updated DESC LIMIT 1"
                
                async with db.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return self._row_to_current_price(row)
                    return None
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            return None
    
    def _row_to_current_price(self, row: aiosqlite.Row) -> CryptocurrencyPrice:
        """Convert database row to CryptocurrencyPrice instance."""
        return CryptocurrencyPrice(
            symbol=row['symbol'],
            name=row['name'],
            current_price=Decimal(str(row['current_price'])),
            currency=row['currency'],
            market_cap=Decimal(str(row['market_cap'])) if row['market_cap'] else None,
            volume_24h=Decimal(str(row['volume_24h'])) if row['volume_24h'] else None,
            price_change_24h=Decimal(str(row['price_change_24h'])) if row['price_change_24h'] else None,
            price_change_percentage_24h=row['price_change_percentage_24h'],
            circulating_supply=Decimal(str(row['circulating_supply'])) if row['circulating_supply'] else None,
            total_supply=Decimal(str(row['total_supply'])) if row['total_supply'] else None,
            max_supply=Decimal(str(row['max_supply'])) if row['max_supply'] else None,
            ath=Decimal(str(row['ath'])) if row['ath'] else None,
            ath_date=datetime.fromisoformat(row['ath_date']) if row['ath_date'] else None,
            atl=Decimal(str(row['atl'])) if row['atl'] else None,
            atl_date=datetime.fromisoformat(row['atl_date']) if row['atl_date'] else None,
            last_updated=datetime.fromisoformat(row['last_updated']),
            data_source=DataSource(row['data_source'])
        )
    
    async def save_historical_prices(self, prices: List[HistoricalPrice]) -> int:
        """Save multiple historical price records.
        
        Args:
            prices: List of HistoricalPrice instances
            
        Returns:
            Number of records saved successfully
        """
        if not prices:
            return 0
        
        saved_count = 0
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for price in prices:
                    try:
                        await db.execute("""
                            INSERT OR REPLACE INTO historical_prices (
                                symbol, timestamp, price, currency, volume, market_cap, data_source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            price.symbol, price.timestamp.isoformat(), float(price.price),
                            price.currency,
                            float(price.volume) if price.volume else None,
                            float(price.market_cap) if price.market_cap else None,
                            price.data_source.value
                        ))
                        saved_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to save historical price for {price.symbol} at {price.timestamp}: {e}")
                
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save historical prices: {e}")
        
        return saved_count
    
    async def get_historical_prices(self, symbol: str, start_date: datetime, 
                                  end_date: datetime, currency: str = "usd") -> List[HistoricalPrice]:
        """Get historical prices for a symbol within date range.
        
        Args:
            symbol: Cryptocurrency symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            currency: Price currency
            
        Returns:
            List of HistoricalPrice instances
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                async with db.execute("""
                    SELECT * FROM historical_prices 
                    WHERE symbol = ? AND currency = ? 
                    AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                """, (symbol.upper(), currency, start_date.isoformat(), end_date.isoformat())) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_historical_price(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []
    
    def _row_to_historical_price(self, row: aiosqlite.Row) -> HistoricalPrice:
        """Convert database row to HistoricalPrice instance."""
        return HistoricalPrice(
            symbol=row['symbol'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            price=Decimal(str(row['price'])),
            currency=row['currency'],
            volume=Decimal(str(row['volume'])) if row['volume'] else None,
            market_cap=Decimal(str(row['market_cap'])) if row['market_cap'] else None,
            data_source=DataSource(row['data_source'])
        )
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> int:
        """Clean up old data beyond retention period.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        deleted_count = 0
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Clean up old historical prices
                cursor = await db.execute("""
                    DELETE FROM historical_prices 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                deleted_count += cursor.rowcount
                
                # Clean up expired cache entries
                cursor = await db.execute("""
                    DELETE FROM cache_entries 
                    WHERE expires_at < ?
                """, (datetime.now(timezone.utc).isoformat(),))
                deleted_count += cursor.rowcount
                
                await db.commit()
                logger.info(f"Cleaned up {deleted_count} old records")
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
        
        return deleted_count
    
    async def close(self):
        """Close database connections."""
        # Close any pooled connections
        for conn in self._connection_pool.values():
            if hasattr(conn, 'close'):
                await conn.close()
        self._connection_pool.clear()
        logger.info("Database connections closed")

"""Data models for cryptocurrency market data."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class DataSource(Enum):
    """Supported data sources."""
    COINGECKO = "coingecko"
    COINMARKETCAP = "coinmarketcap"
    BINANCE = "binance"
    MANUAL = "manual"


class PriceChangeInterval(Enum):
    """Price change intervals."""
    HOUR_1 = "1h"
    HOUR_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    YEAR_1 = "1y"


@dataclass
class CryptocurrencyPrice:
    """Real-time cryptocurrency price data."""
    
    symbol: str
    name: str
    current_price: Decimal
    currency: str = "usd"
    market_cap: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    price_change_24h: Optional[Decimal] = None
    price_change_percentage_24h: Optional[float] = None
    circulating_supply: Optional[Decimal] = None
    total_supply: Optional[Decimal] = None
    max_supply: Optional[Decimal] = None
    ath: Optional[Decimal] = None  # All-time high
    ath_date: Optional[datetime] = None
    atl: Optional[Decimal] = None  # All-time low
    atl_date: Optional[datetime] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_source: DataSource = DataSource.COINGECKO
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        if isinstance(self.current_price, (int, float)):
            self.current_price = Decimal(str(self.current_price))
        
        # Normalize symbol to uppercase
        self.symbol = self.symbol.upper()
        
        # Ensure datetime has timezone info
        if self.last_updated.tzinfo is None:
            self.last_updated = self.last_updated.replace(tzinfo=timezone.utc)
    
    @property
    def price_change_percentage_1h(self) -> Optional[float]:
        """1-hour price change percentage (if available)."""
        return getattr(self, '_price_change_percentage_1h', None)
    
    @price_change_percentage_1h.setter
    def price_change_percentage_1h(self, value: Optional[float]):
        """Set 1-hour price change percentage."""
        self._price_change_percentage_1h = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'current_price': float(self.current_price),
            'currency': self.currency,
            'market_cap': float(self.market_cap) if self.market_cap else None,
            'volume_24h': float(self.volume_24h) if self.volume_24h else None,
            'price_change_24h': float(self.price_change_24h) if self.price_change_24h else None,
            'price_change_percentage_24h': self.price_change_percentage_24h,
            'circulating_supply': float(self.circulating_supply) if self.circulating_supply else None,
            'total_supply': float(self.total_supply) if self.total_supply else None,
            'max_supply': float(self.max_supply) if self.max_supply else None,
            'ath': float(self.ath) if self.ath else None,
            'ath_date': self.ath_date.isoformat() if self.ath_date else None,
            'atl': float(self.atl) if self.atl else None,
            'atl_date': self.atl_date.isoformat() if self.atl_date else None,
            'last_updated': self.last_updated.isoformat(),
            'data_source': self.data_source.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CryptocurrencyPrice':
        """Create instance from dictionary."""
        # Convert string dates back to datetime objects
        if data.get('ath_date'):
            data['ath_date'] = datetime.fromisoformat(data['ath_date'])
        if data.get('atl_date'):
            data['atl_date'] = datetime.fromisoformat(data['atl_date'])
        if data.get('last_updated'):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        
        # Convert data source string back to enum
        if data.get('data_source'):
            data['data_source'] = DataSource(data['data_source'])
        
        return cls(**data)


@dataclass
class HistoricalPrice:
    """Historical price data point."""
    
    symbol: str
    timestamp: datetime
    price: Decimal
    currency: str = "usd"
    volume: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    data_source: DataSource = DataSource.COINGECKO
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        if isinstance(self.price, (int, float)):
            self.price = Decimal(str(self.price))
        
        self.symbol = self.symbol.upper()
        
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


@dataclass
class MarketData:
    """Comprehensive market data for a cryptocurrency."""
    
    symbol: str
    name: str
    current_price: CryptocurrencyPrice
    price_changes: Dict[PriceChangeInterval, float] = field(default_factory=dict)
    historical_prices: List[HistoricalPrice] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_price_change(self, interval: PriceChangeInterval, percentage: float):
        """Add price change for a specific interval."""
        self.price_changes[interval] = percentage
    
    def get_price_change(self, interval: PriceChangeInterval) -> Optional[float]:
        """Get price change for a specific interval."""
        return self.price_changes.get(interval)


@dataclass
class CacheEntry:
    """Cache entry for storing temporary data."""
    
    key: str
    value: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def access(self):
        """Mark cache entry as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class APIResponse:
    """Wrapper for API responses with metadata."""
    
    data: Any
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    response_time: float = 0.0
    data_source: DataSource = DataSource.COINGECKO
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cached: bool = False
    
    @property
    def is_success(self) -> bool:
        """Check if response was successful."""
        return 200 <= self.status_code < 300
    
    def to_json(self) -> str:
        """Convert response data to JSON string."""
        return json.dumps(self.data, default=str)

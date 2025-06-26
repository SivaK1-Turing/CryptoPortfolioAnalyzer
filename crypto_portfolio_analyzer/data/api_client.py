"""Base API client framework with rate limiting and error handling."""

import asyncio
import aiohttp
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import logging

from .models import APIResponse, DataSource, CryptocurrencyPrice, HistoricalPrice

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10  # Maximum burst requests
    backoff_factor: float = 1.5  # Exponential backoff multiplier


@dataclass
class APIClientConfig:
    """Configuration for API clients."""
    
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    headers: Dict[str, str] = field(default_factory=dict)


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire permission to make a request.
        
        Returns:
            True if request is allowed, False if rate limited
        """
        async with self._lock:
            now = time.time()
            
            # Clean up old request times
            minute_ago = now - 60
            self._request_times = [t for t in self._request_times if t > minute_ago]
            
            # Check if we're within rate limits
            if len(self._request_times) >= self.config.requests_per_minute:
                return False
            
            # Record this request
            self._request_times.append(now)
            return True
    
    async def wait_if_needed(self) -> float:
        """Wait if rate limited.
        
        Returns:
            Time waited in seconds
        """
        if await self.acquire():
            return 0.0
        
        # Calculate wait time
        now = time.time()
        oldest_request = min(self._request_times) if self._request_times else now
        wait_time = 60 - (now - oldest_request)
        
        if wait_time > 0:
            logger.info(f"Rate limited, waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
            return wait_time
        
        return 0.0


class BaseAPIClient(ABC):
    """Base class for cryptocurrency API clients."""
    
    def __init__(self, config: APIClientConfig, data_source: DataSource):
        """Initialize API client.
        
        Args:
            config: API client configuration
            data_source: Data source identifier
        """
        self.config = config
        self.data_source = data_source
        self.rate_limiter = RateLimiter(config.rate_limit)
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    async def start(self):
        """Start the API client session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.config.headers
            )
            logger.info(f"Started {self.data_source.value} API client")
    
    async def stop(self):
        """Stop the API client session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info(f"Stopped {self.data_source.value} API client")
    
    async def _make_request(self, method: str, endpoint: str, 
                          params: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make HTTP request with rate limiting and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            
        Returns:
            APIResponse with response data and metadata
        """
        if not self._session:
            await self.start()
        
        # Wait for rate limiting
        wait_time = await self.rate_limiter.wait_if_needed()
        
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        request_headers = {**self.config.headers}
        if headers:
            request_headers.update(headers)
        
        # Add API key if configured
        if self.config.api_key:
            request_headers.update(self._get_auth_headers())
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=request_headers
                ) as response:
                    response_time = time.time() - start_time
                    self._request_count += 1
                    
                    # Read response data
                    if response.content_type == 'application/json':
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    # Create API response
                    api_response = APIResponse(
                        data=data,
                        status_code=response.status,
                        headers=dict(response.headers),
                        response_time=response_time,
                        data_source=self.data_source,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    # Log request details
                    logger.debug(f"{method} {url} -> {response.status} ({response_time:.3f}s)")
                    
                    return api_response
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retries:
                    # Exponential backoff
                    delay = self.config.retry_delay * (self.config.rate_limit.backoff_factor ** attempt)
                    await asyncio.sleep(delay)
        
        # All retries failed
        raise Exception(f"Request failed after {self.config.max_retries + 1} attempts: {last_exception}")
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests.
        
        Returns:
            Dictionary of authentication headers
        """
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str, currency: str = "usd") -> Optional[CryptocurrencyPrice]:
        """Get current price for a cryptocurrency.
        
        Args:
            symbol: Cryptocurrency symbol
            currency: Target currency
            
        Returns:
            CryptocurrencyPrice instance or None if not found
        """
        pass
    
    @abstractmethod
    async def get_multiple_prices(self, symbols: List[str], currency: str = "usd") -> List[CryptocurrencyPrice]:
        """Get current prices for multiple cryptocurrencies.
        
        Args:
            symbols: List of cryptocurrency symbols
            currency: Target currency
            
        Returns:
            List of CryptocurrencyPrice instances
        """
        pass
    
    @abstractmethod
    async def get_historical_prices(self, symbol: str, start_date: datetime, 
                                  end_date: datetime, currency: str = "usd") -> List[HistoricalPrice]:
        """Get historical prices for a cryptocurrency.
        
        Args:
            symbol: Cryptocurrency symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            currency: Target currency
            
        Returns:
            List of HistoricalPrice instances
        """
        pass
    
    async def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies.
        
        Returns:
            List of supported currency codes
        """
        # Default implementation - can be overridden by specific clients
        return ["usd", "eur", "btc", "eth"]
    
    async def health_check(self) -> bool:
        """Check if API is healthy and accessible.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Make a simple request to test connectivity
            response = await self._make_request("GET", "ping")
            return response.is_success
        except Exception as e:
            logger.error(f"Health check failed for {self.data_source.value}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.
        
        Returns:
            Dictionary with client statistics
        """
        return {
            'data_source': self.data_source.value,
            'request_count': self._request_count,
            'base_url': self.config.base_url,
            'has_api_key': bool(self.config.api_key),
            'rate_limit': {
                'requests_per_minute': self.config.rate_limit.requests_per_minute,
                'requests_per_hour': self.config.rate_limit.requests_per_hour
            }
        }


class APIClientManager:
    """Manages multiple API clients with failover support."""
    
    def __init__(self):
        """Initialize API client manager."""
        self._clients: Dict[DataSource, BaseAPIClient] = {}
        self._primary_source: Optional[DataSource] = None
        self._fallback_sources: List[DataSource] = []
    
    def register_client(self, client: BaseAPIClient, is_primary: bool = False):
        """Register an API client.
        
        Args:
            client: API client instance
            is_primary: Whether this is the primary data source
        """
        self._clients[client.data_source] = client
        
        if is_primary:
            self._primary_source = client.data_source
        else:
            self._fallback_sources.append(client.data_source)
        
        logger.info(f"Registered {client.data_source.value} API client")
    
    async def get_current_price(self, symbol: str, currency: str = "usd") -> Optional[CryptocurrencyPrice]:
        """Get current price with failover support.
        
        Args:
            symbol: Cryptocurrency symbol
            currency: Target currency
            
        Returns:
            CryptocurrencyPrice instance or None if not available
        """
        # Try primary source first
        if self._primary_source and self._primary_source in self._clients:
            try:
                client = self._clients[self._primary_source]
                price = await client.get_current_price(symbol, currency)
                if price:
                    return price
            except Exception as e:
                logger.warning(f"Primary source {self._primary_source.value} failed: {e}")
        
        # Try fallback sources
        for source in self._fallback_sources:
            if source in self._clients:
                try:
                    client = self._clients[source]
                    price = await client.get_current_price(symbol, currency)
                    if price:
                        logger.info(f"Used fallback source {source.value} for {symbol}")
                        return price
                except Exception as e:
                    logger.warning(f"Fallback source {source.value} failed: {e}")
        
        return None
    
    async def start_all(self):
        """Start all registered clients."""
        for client in self._clients.values():
            await client.start()
    
    async def stop_all(self):
        """Stop all registered clients."""
        for client in self._clients.values():
            await client.stop()
    
    def get_client(self, data_source: DataSource) -> Optional[BaseAPIClient]:
        """Get specific API client.
        
        Args:
            data_source: Data source to get client for
            
        Returns:
            API client instance or None if not registered
        """
        return self._clients.get(data_source)


# Global API client manager instance
_global_client_manager: Optional[APIClientManager] = None


async def get_client_manager() -> APIClientManager:
    """Get global API client manager instance."""
    global _global_client_manager

    if _global_client_manager is None:
        _global_client_manager = APIClientManager()

    return _global_client_manager

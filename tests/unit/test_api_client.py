"""Tests for API client framework."""

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from crypto_portfolio_analyzer.data.api_client import (
    RateLimiter,
    RateLimitConfig,
    BaseAPIClient,
    APIClientConfig,
    APIClientManager
)
from crypto_portfolio_analyzer.data.models import DataSource, APIResponse


@pytest.fixture
def rate_limit_config():
    """Create a test rate limit configuration."""
    return RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000,
        burst_limit=5,
        backoff_factor=1.5
    )


@pytest.fixture
def api_client_config():
    """Create a test API client configuration."""
    return APIClientConfig(
        base_url="https://api.test.com",
        api_key="test_key",
        timeout=10,
        max_retries=2,
        retry_delay=0.1,
        headers={"User-Agent": "Test-Client"}
    )


class TestRateLimitConfig:
    """Test RateLimitConfig class."""
    
    def test_rate_limit_config_defaults(self):
        """Test default rate limit configuration."""
        config = RateLimitConfig()
        
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.requests_per_day == 10000
        assert config.burst_limit == 10
        assert config.backoff_factor == 1.5
    
    def test_rate_limit_config_custom(self):
        """Test custom rate limit configuration."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=15
        )
        
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_limit == 15


class TestRateLimiter:
    """Test RateLimiter functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self, rate_limit_config):
        """Test successful rate limit acquisition."""
        limiter = RateLimiter(rate_limit_config)
        
        # Should allow initial requests
        for _ in range(5):
            allowed = await limiter.acquire()
            assert allowed
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_blocked(self, rate_limit_config):
        """Test rate limiting when limit is exceeded."""
        # Set very low limit for testing
        rate_limit_config.requests_per_minute = 2
        limiter = RateLimiter(rate_limit_config)
        
        # First two requests should be allowed
        assert await limiter.acquire()
        assert await limiter.acquire()
        
        # Third request should be blocked
        assert not await limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_wait_if_needed(self, rate_limit_config):
        """Test waiting when rate limited."""
        rate_limit_config.requests_per_minute = 1
        limiter = RateLimiter(rate_limit_config)
        
        # First request should not wait
        wait_time = await limiter.wait_if_needed()
        assert wait_time == 0.0
        
        # Second request should wait (but we'll mock time for testing)
        with patch('time.time') as mock_time:
            mock_time.side_effect = [0, 0, 30, 30]  # Simulate 30 seconds passed
            wait_time = await limiter.wait_if_needed()
            # Should wait remaining 30 seconds to complete the minute
            assert wait_time >= 0


class MockAPIClient(BaseAPIClient):
    """Mock API client for testing."""
    
    def _get_auth_headers(self):
        return {"Authorization": f"Bearer {self.config.api_key}"}
    
    async def get_current_price(self, symbol, currency="usd"):
        return None
    
    async def get_multiple_prices(self, symbols, currency="usd"):
        return []
    
    async def get_historical_prices(self, symbol, start_date, end_date, currency="usd"):
        return []


class TestBaseAPIClient:
    """Test BaseAPIClient functionality."""
    
    @pytest.mark.asyncio
    async def test_api_client_lifecycle(self, api_client_config):
        """Test API client start and stop."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        # Initially no session
        assert client._session is None
        
        # Start client
        await client.start()
        assert client._session is not None
        assert isinstance(client._session, aiohttp.ClientSession)
        
        # Stop client
        await client.stop()
        assert client._session is None
    
    @pytest.mark.asyncio
    async def test_api_client_context_manager(self, api_client_config):
        """Test API client as async context manager."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        async with client:
            assert client._session is not None
        
        assert client._session is None
    
    @pytest.mark.asyncio
    async def test_api_client_make_request_success(self, api_client_config):
        """Test successful API request."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content_type = "application/json"
        mock_response.json = AsyncMock(return_value={"price": 50000})
        
        with patch.object(client, '_session') as mock_session:
            mock_session.request.return_value.__aenter__.return_value = mock_response
            
            response = await client._make_request("GET", "test")
            
            assert response.status_code == 200
            assert response.data == {"price": 50000}
            assert response.data_source == DataSource.COINGECKO
            assert response.is_success
            assert isinstance(response.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_api_client_make_request_with_auth(self, api_client_config):
        """Test API request with authentication headers."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content_type = "application/json"
        mock_response.json = AsyncMock(return_value={})
        
        with patch.object(client, '_session') as mock_session:
            mock_session.request.return_value.__aenter__.return_value = mock_response
            
            await client._make_request("GET", "test")
            
            # Verify auth headers were added
            call_args = mock_session.request.call_args
            headers = call_args[1]['headers']
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test_key"
    
    @pytest.mark.asyncio
    async def test_api_client_make_request_retry(self, api_client_config):
        """Test API request retry logic."""
        api_client_config.max_retries = 2
        api_client_config.retry_delay = 0.01  # Fast retry for testing
        
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        # Mock failing then successful response
        mock_response_fail = AsyncMock()
        mock_response_fail.status = 500
        
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.headers = {}
        mock_response_success.content_type = "application/json"
        mock_response_success.json = AsyncMock(return_value={"success": True})
        
        with patch.object(client, '_session') as mock_session:
            # First call fails, second succeeds
            mock_session.request.return_value.__aenter__.side_effect = [
                Exception("Network error"),
                mock_response_success
            ]
            
            response = await client._make_request("GET", "test")
            
            assert response.status_code == 200
            assert response.data == {"success": True}
            
            # Should have made 2 attempts
            assert mock_session.request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_api_client_make_request_max_retries_exceeded(self, api_client_config):
        """Test API request when max retries are exceeded."""
        api_client_config.max_retries = 1
        api_client_config.retry_delay = 0.01
        
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        with patch.object(client, '_session') as mock_session:
            # All attempts fail
            mock_session.request.return_value.__aenter__.side_effect = Exception("Network error")
            
            with pytest.raises(Exception, match="Request failed after 2 attempts"):
                await client._make_request("GET", "test")
    
    @pytest.mark.asyncio
    async def test_api_client_health_check(self, api_client_config):
        """Test API client health check."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        # Mock successful ping response
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data={"status": "ok"},
                status_code=200
            )
            
            healthy = await client.health_check()
            assert healthy
            
            mock_request.assert_called_once_with("GET", "ping")
    
    @pytest.mark.asyncio
    async def test_api_client_health_check_failure(self, api_client_config):
        """Test API client health check failure."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        # Mock failed ping response
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("Connection failed")
            
            healthy = await client.health_check()
            assert not healthy
    
    def test_api_client_get_stats(self, api_client_config):
        """Test API client statistics."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        client._request_count = 42
        
        stats = client.get_stats()
        
        assert stats['data_source'] == 'coingecko'
        assert stats['request_count'] == 42
        assert stats['base_url'] == 'https://api.test.com'
        assert stats['has_api_key'] is True
        assert stats['rate_limit']['requests_per_minute'] == 60
    
    @pytest.mark.asyncio
    async def test_api_client_get_supported_currencies(self, api_client_config):
        """Test getting supported currencies (default implementation)."""
        client = MockAPIClient(api_client_config, DataSource.COINGECKO)
        
        currencies = await client.get_supported_currencies()
        
        assert isinstance(currencies, list)
        assert "usd" in currencies
        assert "eur" in currencies
        assert "btc" in currencies


class TestAPIClientManager:
    """Test APIClientManager functionality."""
    
    def test_api_client_manager_register_client(self):
        """Test registering API clients."""
        manager = APIClientManager()
        
        # Create mock clients
        config = APIClientConfig(base_url="https://api.test.com")
        client1 = MockAPIClient(config, DataSource.COINGECKO)
        client2 = MockAPIClient(config, DataSource.COINMARKETCAP)
        
        # Register clients
        manager.register_client(client1, is_primary=True)
        manager.register_client(client2, is_primary=False)
        
        assert manager._primary_source == DataSource.COINGECKO
        assert DataSource.COINMARKETCAP in manager._fallback_sources
        assert manager.get_client(DataSource.COINGECKO) == client1
        assert manager.get_client(DataSource.COINMARKETCAP) == client2
    
    @pytest.mark.asyncio
    async def test_api_client_manager_get_current_price_primary(self):
        """Test getting current price from primary source."""
        manager = APIClientManager()
        
        # Mock primary client
        config = APIClientConfig(base_url="https://api.test.com")
        primary_client = MockAPIClient(config, DataSource.COINGECKO)
        
        with patch.object(primary_client, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = "mock_price"
            
            manager.register_client(primary_client, is_primary=True)
            
            price = await manager.get_current_price("BTC", "usd")
            
            assert price == "mock_price"
            mock_get_price.assert_called_once_with("BTC", "usd")
    
    @pytest.mark.asyncio
    async def test_api_client_manager_get_current_price_fallback(self):
        """Test getting current price with fallback to secondary source."""
        manager = APIClientManager()
        
        # Mock clients
        config = APIClientConfig(base_url="https://api.test.com")
        primary_client = MockAPIClient(config, DataSource.COINGECKO)
        fallback_client = MockAPIClient(config, DataSource.COINMARKETCAP)
        
        with patch.object(primary_client, 'get_current_price') as mock_primary:
            with patch.object(fallback_client, 'get_current_price') as mock_fallback:
                # Primary fails, fallback succeeds
                mock_primary.side_effect = Exception("Primary failed")
                mock_fallback.return_value = "fallback_price"
                
                manager.register_client(primary_client, is_primary=True)
                manager.register_client(fallback_client, is_primary=False)
                
                price = await manager.get_current_price("BTC", "usd")
                
                assert price == "fallback_price"
                mock_primary.assert_called_once()
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_client_manager_get_current_price_all_fail(self):
        """Test getting current price when all sources fail."""
        manager = APIClientManager()
        
        # Mock clients that both fail
        config = APIClientConfig(base_url="https://api.test.com")
        primary_client = MockAPIClient(config, DataSource.COINGECKO)
        fallback_client = MockAPIClient(config, DataSource.COINMARKETCAP)
        
        with patch.object(primary_client, 'get_current_price') as mock_primary:
            with patch.object(fallback_client, 'get_current_price') as mock_fallback:
                mock_primary.side_effect = Exception("Primary failed")
                mock_fallback.side_effect = Exception("Fallback failed")
                
                manager.register_client(primary_client, is_primary=True)
                manager.register_client(fallback_client, is_primary=False)
                
                price = await manager.get_current_price("BTC", "usd")
                
                assert price is None
    
    @pytest.mark.asyncio
    async def test_api_client_manager_start_stop_all(self):
        """Test starting and stopping all clients."""
        manager = APIClientManager()
        
        # Mock clients
        config = APIClientConfig(base_url="https://api.test.com")
        client1 = MockAPIClient(config, DataSource.COINGECKO)
        client2 = MockAPIClient(config, DataSource.COINMARKETCAP)
        
        with patch.object(client1, 'start') as mock_start1:
            with patch.object(client1, 'stop') as mock_stop1:
                with patch.object(client2, 'start') as mock_start2:
                    with patch.object(client2, 'stop') as mock_stop2:
                        
                        manager.register_client(client1)
                        manager.register_client(client2)
                        
                        # Start all
                        await manager.start_all()
                        mock_start1.assert_called_once()
                        mock_start2.assert_called_once()
                        
                        # Stop all
                        await manager.stop_all()
                        mock_stop1.assert_called_once()
                        mock_stop2.assert_called_once()
    
    def test_api_client_manager_get_client(self):
        """Test getting specific client."""
        manager = APIClientManager()
        
        config = APIClientConfig(base_url="https://api.test.com")
        client = MockAPIClient(config, DataSource.COINGECKO)
        
        manager.register_client(client)
        
        # Should return the registered client
        retrieved = manager.get_client(DataSource.COINGECKO)
        assert retrieved == client
        
        # Should return None for unregistered source
        assert manager.get_client(DataSource.BINANCE) is None


class TestAPIResponse:
    """Test APIResponse model in API context."""

    def test_api_response_creation(self):
        """Test creating APIResponse."""
        response = APIResponse(
            data={"test": "data"},
            status_code=200,
            headers={"Content-Type": "application/json"},
            response_time=0.5,
            data_source=DataSource.COINGECKO
        )

        assert response.data == {"test": "data"}
        assert response.status_code == 200
        assert response.is_success
        assert response.data_source == DataSource.COINGECKO
        assert not response.cached

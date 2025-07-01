"""Tests for CoinGecko API client."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.data.clients.coingecko import CoinGeckoClient
from crypto_portfolio_analyzer.data.models import DataSource, APIResponse


@pytest.fixture
def coingecko_client():
    """Create a CoinGecko client for testing."""
    return CoinGeckoClient(api_key="test_key")


@pytest.fixture
def mock_coins_list_response():
    """Mock response for coins list endpoint."""
    return [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
        {"id": "cardano", "symbol": "ada", "name": "Cardano"}
    ]


@pytest.fixture
def mock_price_response():
    """Mock response for simple price endpoint."""
    return {
        "bitcoin": {
            "usd": 50000,
            "usd_market_cap": 1000000000000,
            "usd_24h_vol": 50000000000,
            "usd_24h_change": 2.5,
            "last_updated_at": 1640995200  # 2022-01-01 00:00:00 UTC
        }
    }


@pytest.fixture
def mock_historical_response():
    """Mock response for historical data endpoint."""
    return {
        "prices": [
            [1640995200000, 47000],  # 2022-01-01 00:00:00 UTC
            [1641081600000, 48000],  # 2022-01-02 00:00:00 UTC
            [1641168000000, 49000],  # 2022-01-03 00:00:00 UTC
        ],
        "total_volumes": [
            [1640995200000, 30000000000],
            [1641081600000, 31000000000],
            [1641168000000, 32000000000],
        ],
        "market_caps": [
            [1640995200000, 900000000000],
            [1641081600000, 920000000000],
            [1641168000000, 940000000000],
        ]
    }


class TestCoinGeckoClient:
    """Test CoinGecko client functionality."""
    
    def test_coingecko_client_initialization(self):
        """Test CoinGecko client initialization."""
        # Without API key
        client = CoinGeckoClient()
        assert client.data_source == DataSource.COINGECKO
        assert client.config.base_url == "https://api.coingecko.com/api/v3"
        assert client.config.api_key is None
        assert client.config.rate_limit.requests_per_minute == 10  # Free tier
        
        # With API key
        client_with_key = CoinGeckoClient(api_key="test_key")
        assert client_with_key.config.api_key == "test_key"
        assert client_with_key.config.rate_limit.requests_per_minute == 50  # Paid tier
    
    def test_coingecko_auth_headers(self, coingecko_client):
        """Test authentication header generation."""
        headers = coingecko_client._get_auth_headers()
        assert headers == {"x-cg-demo-api-key": "test_key"}
        
        # Test without API key
        client_no_key = CoinGeckoClient()
        headers_no_key = client_no_key._get_auth_headers()
        assert headers_no_key == {}
    
    @pytest.mark.asyncio
    async def test_get_coin_id_success(self, coingecko_client, mock_coins_list_response):
        """Test successful coin ID retrieval."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data=mock_coins_list_response,
                status_code=200
            )
            
            coin_id = await coingecko_client._get_coin_id("btc")
            assert coin_id == "bitcoin"
            
            # Should cache the result
            coin_id_cached = await coingecko_client._get_coin_id("btc")
            assert coin_id_cached == "bitcoin"
            
            # Should only make one API call due to caching
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_coin_id_not_found(self, coingecko_client, mock_coins_list_response):
        """Test coin ID retrieval for non-existent symbol."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data=mock_coins_list_response,
                status_code=200
            )
            
            coin_id = await coingecko_client._get_coin_id("nonexistent")
            assert coin_id is None
    
    @pytest.mark.asyncio
    async def test_get_coin_id_api_error(self, coingecko_client):
        """Test coin ID retrieval when API fails."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            coin_id = await coingecko_client._get_coin_id("btc")
            assert coin_id is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_success(self, coingecko_client, mock_coins_list_response, mock_price_response):
        """Test successful current price retrieval."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            # Mock coins list call
            mock_request.side_effect = [
                APIResponse(data=mock_coins_list_response, status_code=200),
                APIResponse(data=mock_price_response, status_code=200)
            ]
            
            price = await coingecko_client.get_current_price("BTC", "usd")
            
            assert price is not None
            assert price.symbol == "BTC"
            assert price.current_price == Decimal("50000")
            assert price.currency == "usd"
            assert price.market_cap == Decimal("1000000000000")
            assert price.volume_24h == Decimal("50000000000")
            assert price.price_change_percentage_24h == 2.5
            assert price.data_source == DataSource.COINGECKO
            assert isinstance(price.last_updated, datetime)
    
    @pytest.mark.asyncio
    async def test_get_current_price_coin_not_found(self, coingecko_client):
        """Test current price retrieval when coin ID is not found."""
        with patch.object(coingecko_client, '_get_coin_id') as mock_get_id:
            mock_get_id.return_value = None
            
            price = await coingecko_client.get_current_price("NONEXISTENT", "usd")
            assert price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_api_error(self, coingecko_client, mock_coins_list_response):
        """Test current price retrieval when price API fails."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            # First call succeeds (coins list), second fails (price)
            mock_request.side_effect = [
                APIResponse(data=mock_coins_list_response, status_code=200),
                Exception("Price API Error")
            ]
            
            price = await coingecko_client.get_current_price("BTC", "usd")
            assert price is None
    
    @pytest.mark.asyncio
    async def test_get_multiple_prices_success(self, coingecko_client, mock_coins_list_response):
        """Test successful multiple prices retrieval."""
        mock_multi_price_response = {
            "bitcoin": {
                "usd": 50000,
                "usd_market_cap": 1000000000000,
                "usd_24h_vol": 50000000000,
                "usd_24h_change": 2.5,
                "last_updated_at": 1640995200
            },
            "ethereum": {
                "usd": 3000,
                "usd_market_cap": 400000000000,
                "usd_24h_vol": 20000000000,
                "usd_24h_change": 1.8,
                "last_updated_at": 1640995200
            }
        }
        
        with patch.object(coingecko_client, '_make_request') as mock_request:
            # Mock the coins list call (will be called once and cached)
            def mock_request_side_effect(method, endpoint, params=None):
                if endpoint == "coins/list":
                    return APIResponse(data=mock_coins_list_response, status_code=200)
                elif endpoint == "simple/price":
                    return APIResponse(data=mock_multi_price_response, status_code=200)
                else:
                    raise Exception(f"Unexpected endpoint: {endpoint}")

            mock_request.side_effect = mock_request_side_effect
            
            prices = await coingecko_client.get_multiple_prices(["BTC", "ETH"], "usd")
            
            assert len(prices) == 2
            
            # Check BTC price
            btc_price = next(p for p in prices if p.symbol == "BTC")
            assert btc_price.current_price == Decimal("50000")
            assert btc_price.data_source == DataSource.COINGECKO
            
            # Check ETH price
            eth_price = next(p for p in prices if p.symbol == "ETH")
            assert eth_price.current_price == Decimal("3000")
    
    @pytest.mark.asyncio
    async def test_get_multiple_prices_empty_list(self, coingecko_client):
        """Test multiple prices retrieval with empty symbol list."""
        prices = await coingecko_client.get_multiple_prices([], "usd")
        assert prices == []
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_success(self, coingecko_client, mock_coins_list_response, mock_historical_response):
        """Test successful historical prices retrieval."""
        start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 1, 3, tzinfo=timezone.utc)
        
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = [
                APIResponse(data=mock_coins_list_response, status_code=200),
                APIResponse(data=mock_historical_response, status_code=200)
            ]
            
            historical_prices = await coingecko_client.get_historical_prices(
                "BTC", start_date, end_date, "usd"
            )
            
            assert len(historical_prices) == 3
            
            # Check first price
            first_price = historical_prices[0]
            assert first_price.symbol == "BTC"
            assert first_price.price == Decimal("47000")
            assert first_price.currency == "usd"
            assert first_price.volume == Decimal("30000000000")
            assert first_price.market_cap == Decimal("900000000000")
            assert first_price.data_source == DataSource.COINGECKO
            
            # Verify timestamps are within range
            for price in historical_prices:
                assert start_date <= price.timestamp <= end_date
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_short_period(self, coingecko_client, mock_coins_list_response, mock_historical_response):
        """Test historical prices for short time period (uses daily data)."""
        start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 1, 2, tzinfo=timezone.utc)  # 1 day
        
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = [
                APIResponse(data=mock_coins_list_response, status_code=200),
                APIResponse(data=mock_historical_response, status_code=200)
            ]
            
            await coingecko_client.get_historical_prices("BTC", start_date, end_date, "usd")
            
            # Should use market_chart endpoint with days=1
            price_call = mock_request.call_args_list[1]
            assert "market_chart" in price_call[0][1]
            assert price_call[1]["params"]["days"] == "1"
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_long_period(self, coingecko_client, mock_coins_list_response, mock_historical_response):
        """Test historical prices for long time period (uses range endpoint)."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 1, 1, tzinfo=timezone.utc)  # 365 days
        
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = [
                APIResponse(data=mock_coins_list_response, status_code=200),
                APIResponse(data=mock_historical_response, status_code=200)
            ]
            
            await coingecko_client.get_historical_prices("BTC", start_date, end_date, "usd")
            
            # Should use market_chart/range endpoint
            price_call = mock_request.call_args_list[1]
            assert "market_chart/range" in price_call[0][1]
            assert "from" in price_call[1]["params"]
            assert "to" in price_call[1]["params"]
    
    @pytest.mark.asyncio
    async def test_get_historical_prices_coin_not_found(self, coingecko_client):
        """Test historical prices when coin ID is not found."""
        with patch.object(coingecko_client, '_get_coin_id') as mock_get_id:
            mock_get_id.return_value = None
            
            start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(2022, 1, 3, tzinfo=timezone.utc)
            
            prices = await coingecko_client.get_historical_prices(
                "NONEXISTENT", start_date, end_date, "usd"
            )
            assert prices == []
    
    @pytest.mark.asyncio
    async def test_get_supported_currencies_success(self, coingecko_client):
        """Test successful supported currencies retrieval."""
        mock_currencies = ["usd", "eur", "btc", "eth", "bnb"]
        
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data=mock_currencies,
                status_code=200
            )
            
            currencies = await coingecko_client.get_supported_currencies()
            assert currencies == mock_currencies
    
    @pytest.mark.asyncio
    async def test_get_supported_currencies_api_error(self, coingecko_client):
        """Test supported currencies when API fails (returns defaults)."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            currencies = await coingecko_client.get_supported_currencies()
            
            # Should return default currencies
            assert isinstance(currencies, list)
            assert "usd" in currencies
            assert "eur" in currencies
            assert "btc" in currencies
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, coingecko_client):
        """Test successful health check."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data={"gecko_says": "(V3) To the Moon!"},
                status_code=200
            )
            
            healthy = await coingecko_client.health_check()
            assert healthy
    
    @pytest.mark.asyncio
    async def test_health_check_wrong_response(self, coingecko_client):
        """Test health check with wrong response."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.return_value = APIResponse(
                data={"gecko_says": "Wrong message"},
                status_code=200
            )
            
            healthy = await coingecko_client.health_check()
            assert not healthy
    
    @pytest.mark.asyncio
    async def test_health_check_api_error(self, coingecko_client):
        """Test health check when API fails."""
        with patch.object(coingecko_client, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            healthy = await coingecko_client.health_check()
            assert not healthy

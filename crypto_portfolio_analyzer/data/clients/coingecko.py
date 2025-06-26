"""CoinGecko API client implementation."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging

from ..api_client import BaseAPIClient, APIClientConfig, RateLimitConfig
from ..models import CryptocurrencyPrice, HistoricalPrice, DataSource

logger = logging.getLogger(__name__)


class CoinGeckoClient(BaseAPIClient):
    """CoinGecko API client for cryptocurrency data."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize CoinGecko client.
        
        Args:
            api_key: Optional CoinGecko API key for higher rate limits
        """
        # CoinGecko rate limits (free tier)
        rate_limit = RateLimitConfig(
            requests_per_minute=50 if api_key else 10,
            requests_per_hour=1000 if api_key else 100,
            requests_per_day=10000 if api_key else 1000
        )
        
        config = APIClientConfig(
            base_url="https://api.coingecko.com/api/v3",
            api_key=api_key,
            timeout=30,
            max_retries=3,
            rate_limit=rate_limit,
            headers={
                "Accept": "application/json",
                "User-Agent": "CryptoPortfolioAnalyzer/1.0"
            }
        )
        
        super().__init__(config, DataSource.COINGECKO)
        
        # Cache for coin ID mappings
        self._coin_id_cache: Dict[str, str] = {}
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for CoinGecko API.
        
        Returns:
            Dictionary of authentication headers
        """
        if self.config.api_key:
            return {"x-cg-demo-api-key": self.config.api_key}
        return {}
    
    async def _get_coin_id(self, symbol: str) -> Optional[str]:
        """Get CoinGecko coin ID for a symbol.
        
        Args:
            symbol: Cryptocurrency symbol
            
        Returns:
            CoinGecko coin ID or None if not found
        """
        symbol = symbol.lower()
        
        # Check cache first
        if symbol in self._coin_id_cache:
            return self._coin_id_cache[symbol]
        
        try:
            # Get coins list from CoinGecko
            response = await self._make_request("GET", "coins/list")
            
            if response.is_success:
                coins = response.data
                for coin in coins:
                    coin_symbol = coin.get('symbol', '').lower()
                    coin_id = coin.get('id', '')
                    
                    # Cache the mapping
                    self._coin_id_cache[coin_symbol] = coin_id
                    
                    if coin_symbol == symbol:
                        return coin_id
            
        except Exception as e:
            logger.error(f"Failed to get coin ID for {symbol}: {e}")
        
        return None
    
    async def get_current_price(self, symbol: str, currency: str = "usd") -> Optional[CryptocurrencyPrice]:
        """Get current price for a cryptocurrency.
        
        Args:
            symbol: Cryptocurrency symbol
            currency: Target currency
            
        Returns:
            CryptocurrencyPrice instance or None if not found
        """
        coin_id = await self._get_coin_id(symbol)
        if not coin_id:
            logger.warning(f"Could not find CoinGecko ID for symbol {symbol}")
            return None
        
        try:
            params = {
                "ids": coin_id,
                "vs_currencies": currency,
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            response = await self._make_request("GET", "simple/price", params=params)
            
            if response.is_success and coin_id in response.data:
                coin_data = response.data[coin_id]
                
                return CryptocurrencyPrice(
                    symbol=symbol.upper(),
                    name=coin_id.replace('-', ' ').title(),
                    current_price=Decimal(str(coin_data.get(currency, 0))),
                    currency=currency,
                    market_cap=Decimal(str(coin_data.get(f"{currency}_market_cap", 0))) if coin_data.get(f"{currency}_market_cap") else None,
                    volume_24h=Decimal(str(coin_data.get(f"{currency}_24h_vol", 0))) if coin_data.get(f"{currency}_24h_vol") else None,
                    price_change_percentage_24h=coin_data.get(f"{currency}_24h_change"),
                    last_updated=datetime.fromtimestamp(coin_data.get("last_updated_at", 0), tz=timezone.utc),
                    data_source=DataSource.COINGECKO
                )
                
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
        
        return None
    
    async def get_multiple_prices(self, symbols: List[str], currency: str = "usd") -> List[CryptocurrencyPrice]:
        """Get current prices for multiple cryptocurrencies.
        
        Args:
            symbols: List of cryptocurrency symbols
            currency: Target currency
            
        Returns:
            List of CryptocurrencyPrice instances
        """
        if not symbols:
            return []
        
        # Get coin IDs for all symbols
        coin_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            coin_id = await self._get_coin_id(symbol)
            if coin_id:
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = symbol.upper()
        
        if not coin_ids:
            return []
        
        try:
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": currency,
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            response = await self._make_request("GET", "simple/price", params=params)
            
            if response.is_success:
                prices = []
                
                for coin_id, coin_data in response.data.items():
                    symbol = symbol_to_id.get(coin_id, coin_id.upper())
                    
                    price = CryptocurrencyPrice(
                        symbol=symbol,
                        name=coin_id.replace('-', ' ').title(),
                        current_price=Decimal(str(coin_data.get(currency, 0))),
                        currency=currency,
                        market_cap=Decimal(str(coin_data.get(f"{currency}_market_cap", 0))) if coin_data.get(f"{currency}_market_cap") else None,
                        volume_24h=Decimal(str(coin_data.get(f"{currency}_24h_vol", 0))) if coin_data.get(f"{currency}_24h_vol") else None,
                        price_change_percentage_24h=coin_data.get(f"{currency}_24h_change"),
                        last_updated=datetime.fromtimestamp(coin_data.get("last_updated_at", 0), tz=timezone.utc),
                        data_source=DataSource.COINGECKO
                    )
                    
                    prices.append(price)
                
                return prices
                
        except Exception as e:
            logger.error(f"Failed to get multiple prices: {e}")
        
        return []
    
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
        coin_id = await self._get_coin_id(symbol)
        if not coin_id:
            logger.warning(f"Could not find CoinGecko ID for symbol {symbol}")
            return []
        
        try:
            # Calculate days between dates
            days = (end_date - start_date).days
            
            if days <= 1:
                # Use hourly data for short periods
                endpoint = f"coins/{coin_id}/market_chart"
                params = {
                    "vs_currency": currency,
                    "days": "1"
                }
            elif days <= 90:
                # Use daily data for medium periods
                endpoint = f"coins/{coin_id}/market_chart"
                params = {
                    "vs_currency": currency,
                    "days": str(days)
                }
            else:
                # Use range endpoint for longer periods
                endpoint = f"coins/{coin_id}/market_chart/range"
                params = {
                    "vs_currency": currency,
                    "from": str(int(start_date.timestamp())),
                    "to": str(int(end_date.timestamp()))
                }
            
            response = await self._make_request("GET", endpoint, params=params)
            
            if response.is_success:
                prices_data = response.data.get("prices", [])
                volumes_data = response.data.get("total_volumes", [])
                market_caps_data = response.data.get("market_caps", [])
                
                # Create volume and market cap lookups
                volumes = {int(item[0]): item[1] for item in volumes_data}
                market_caps = {int(item[0]): item[1] for item in market_caps_data}
                
                historical_prices = []
                
                for price_data in prices_data:
                    timestamp_ms = int(price_data[0])
                    price = Decimal(str(price_data[1]))
                    
                    # Convert timestamp to datetime
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                    
                    # Filter by date range
                    if start_date <= timestamp <= end_date:
                        historical_price = HistoricalPrice(
                            symbol=symbol.upper(),
                            timestamp=timestamp,
                            price=price,
                            currency=currency,
                            volume=Decimal(str(volumes.get(timestamp_ms, 0))) if volumes.get(timestamp_ms) else None,
                            market_cap=Decimal(str(market_caps.get(timestamp_ms, 0))) if market_caps.get(timestamp_ms) else None,
                            data_source=DataSource.COINGECKO
                        )
                        
                        historical_prices.append(historical_price)
                
                return historical_prices
                
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
        
        return []
    
    async def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies from CoinGecko.
        
        Returns:
            List of supported currency codes
        """
        try:
            response = await self._make_request("GET", "simple/supported_vs_currencies")
            
            if response.is_success:
                return response.data
                
        except Exception as e:
            logger.error(f"Failed to get supported currencies: {e}")
        
        # Return default currencies if API call fails
        return ["usd", "eur", "btc", "eth", "bnb", "xrp", "ada", "sol", "dot", "matic"]
    
    async def health_check(self) -> bool:
        """Check if CoinGecko API is healthy.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = await self._make_request("GET", "ping")
            return response.is_success and response.data.get("gecko_says") == "(V3) To the Moon!"
        except Exception as e:
            logger.error(f"CoinGecko health check failed: {e}")
            return False

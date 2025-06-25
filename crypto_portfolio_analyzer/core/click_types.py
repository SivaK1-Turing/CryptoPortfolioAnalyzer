"""
Custom Click parameter types with remote schema validation and autocompletion.

This module provides enhanced Click parameter types that can pull valid values
from remote JSON schemas, cache them locally with ETag validation, and provide
interactive autocompletion for shell environments.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import click
import requests

logger = logging.getLogger(__name__)


class SchemaValidatedChoice(click.Choice):
    """
    Custom Click Choice parameter that validates against a remote JSON Schema.
    
    This parameter type fetches valid values from a remote JSON schema,
    caches them locally with ETag validation for performance, and provides
    interactive autocompletion in supported shells.
    """
    
    def __init__(
        self,
        schema_url: str,
        schema_path: str = "enum",
        cache_dir: Optional[Path] = None,
        cache_ttl: int = 3600,
        case_sensitive: bool = True,
        timeout: int = 10,
        fallback_choices: Optional[List[str]] = None
    ):
        """
        Initialize the schema-validated choice parameter.
        
        Args:
            schema_url: URL to the JSON schema containing valid choices
            schema_path: JSONPath to the enum values in the schema (default: "enum")
            cache_dir: Directory for caching schema data (default: ~/.cache/crypto-portfolio)
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
            case_sensitive: Whether choices are case sensitive
            timeout: HTTP request timeout in seconds
            fallback_choices: Fallback choices if schema fetch fails
        """
        self.schema_url = schema_url
        self.schema_path = schema_path
        self.cache_dir = cache_dir or Path.home() / ".cache" / "crypto-portfolio"
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.fallback_choices = fallback_choices or []
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize with cached or fetched choices
        choices = self._get_choices()
        super().__init__(choices, case_sensitive=case_sensitive)
    
    def _get_cache_file(self) -> Path:
        """Get the cache file path for this schema."""
        # Create a safe filename from the URL
        url_hash = str(hash(self.schema_url))
        return self.cache_dir / f"schema_{url_hash}.json"
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """Check if the cache file is still valid."""
        if not cache_file.exists():
            return False
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check TTL
            cached_time = cache_data.get('timestamp', 0)
            if time.time() - cached_time > self.cache_ttl:
                return False
            
            return True
            
        except (json.JSONDecodeError, KeyError, OSError):
            return False
    
    def _fetch_schema(self) -> Optional[Dict[str, Any]]:
        """Fetch the schema from the remote URL."""
        try:
            # Get cached ETag if available
            cache_file = self._get_cache_file()
            etag = None
            
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                        etag = cache_data.get('etag')
                except (json.JSONDecodeError, OSError):
                    pass
            
            # Prepare headers
            headers = {'User-Agent': 'crypto-portfolio-analyzer/1.0'}
            if etag:
                headers['If-None-Match'] = etag
            
            # Fetch schema
            response = requests.get(
                self.schema_url,
                headers=headers,
                timeout=self.timeout
            )
            
            # Handle 304 Not Modified
            if response.status_code == 304:
                logger.debug(f"Schema not modified: {self.schema_url}")
                return None
            
            response.raise_for_status()
            schema = response.json()
            
            # Cache the schema with metadata
            cache_data = {
                'schema': schema,
                'timestamp': time.time(),
                'etag': response.headers.get('ETag'),
                'url': self.schema_url
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Fetched and cached schema: {self.schema_url}")
            return schema
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch schema from {self.schema_url}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in schema from {self.schema_url}: {e}")
            return None
    
    def _extract_choices_from_schema(self, schema: Dict[str, Any]) -> List[str]:
        """Extract valid choices from the schema."""
        try:
            # Simple JSONPath implementation for common cases
            if self.schema_path == "enum":
                return schema.get("enum", [])
            
            # Handle nested paths like "properties.symbol.enum"
            parts = self.schema_path.split('.')
            current = schema
            
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    logger.warning(f"Path {self.schema_path} not found in schema")
                    return []
            
            if isinstance(current, list):
                return [str(item) for item in current]
            else:
                logger.warning(f"Expected list at {self.schema_path}, got {type(current)}")
                return []
                
        except Exception as e:
            logger.warning(f"Error extracting choices from schema: {e}")
            return []
    
    def _get_choices(self) -> List[str]:
        """Get the list of valid choices."""
        cache_file = self._get_cache_file()
        
        # Try to use cached data if valid
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    schema = cache_data['schema']
                    choices = self._extract_choices_from_schema(schema)
                    if choices:
                        logger.debug(f"Using cached choices: {len(choices)} items")
                        return choices
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        
        # Fetch fresh schema
        schema = self._fetch_schema()
        if schema:
            choices = self._extract_choices_from_schema(schema)
            if choices:
                return choices
        
        # Use cached data even if expired as fallback
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    schema = cache_data['schema']
                    choices = self._extract_choices_from_schema(schema)
                    if choices:
                        logger.info(f"Using expired cached choices: {len(choices)} items")
                        return choices
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        
        # Final fallback
        logger.warning(f"Using fallback choices for {self.schema_url}")
        return self.fallback_choices
    
    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> List[click.shell_completion.CompletionItem]:
        """Provide shell autocompletion."""
        # Refresh choices if needed
        if not self._is_cache_valid(self._get_cache_file()):
            try:
                self.choices = self._get_choices()
            except Exception:
                pass  # Use existing choices
        
        # Filter choices based on incomplete input
        matches = []
        for choice in self.choices:
            if choice.startswith(incomplete):
                matches.append(click.shell_completion.CompletionItem(choice))
        
        return matches


class CryptocurrencySymbol(SchemaValidatedChoice):
    """
    Specialized parameter type for cryptocurrency symbols.
    
    Fetches valid cryptocurrency symbols from CoinGecko's API
    and provides autocompletion for symbol selection.
    """
    
    def __init__(self, **kwargs):
        # Default configuration for cryptocurrency symbols
        defaults = {
            'schema_url': 'https://api.coingecko.com/api/v3/coins/list',
            'schema_path': 'symbol',  # Will be handled specially
            'cache_ttl': 86400,  # 24 hours
            'case_sensitive': False,
            'fallback_choices': ['btc', 'eth', 'ada', 'dot', 'link', 'ltc', 'xrp']
        }
        defaults.update(kwargs)
        
        # Don't call parent __init__ yet
        self.schema_url = defaults['schema_url']
        self.schema_path = defaults['schema_path']
        self.cache_dir = defaults.get('cache_dir') or Path.home() / ".cache" / "crypto-portfolio"
        self.cache_ttl = defaults['cache_ttl']
        self.timeout = defaults.get('timeout', 10)
        self.fallback_choices = defaults['fallback_choices']
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize with cached or fetched choices
        choices = self._get_crypto_symbols()
        click.Choice.__init__(self, choices, case_sensitive=defaults['case_sensitive'])
    
    def _get_crypto_symbols(self) -> List[str]:
        """Get cryptocurrency symbols from CoinGecko API."""
        cache_file = self._get_cache_file()
        
        # Try cached data first
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    symbols = cache_data.get('symbols', [])
                    if symbols:
                        logger.debug(f"Using cached crypto symbols: {len(symbols)} items")
                        return symbols
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        
        # Fetch from API
        try:
            response = requests.get(
                self.schema_url,
                timeout=self.timeout,
                headers={'User-Agent': 'crypto-portfolio-analyzer/1.0'}
            )
            response.raise_for_status()
            
            coins_data = response.json()
            symbols = [coin['symbol'].lower() for coin in coins_data if 'symbol' in coin]
            
            # Remove duplicates and sort
            symbols = sorted(list(set(symbols)))
            
            # Cache the symbols
            cache_data = {
                'symbols': symbols,
                'timestamp': time.time(),
                'url': self.schema_url
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Fetched and cached {len(symbols)} crypto symbols")
            return symbols
            
        except Exception as e:
            logger.warning(f"Failed to fetch crypto symbols: {e}")
            
            # Try expired cache as fallback
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                        symbols = cache_data.get('symbols', [])
                        if symbols:
                            logger.info(f"Using expired cached symbols: {len(symbols)} items")
                            return symbols
                except (json.JSONDecodeError, KeyError, OSError):
                    pass
            
            # Final fallback
            logger.warning("Using fallback crypto symbols")
            return self.fallback_choices


# Convenience function to create cryptocurrency symbol parameter
def cryptocurrency_symbol(**kwargs) -> CryptocurrencySymbol:
    """Create a cryptocurrency symbol parameter type."""
    return CryptocurrencySymbol(**kwargs)


# Example usage in Click commands:
"""
@click.command()
@click.option('--symbol', type=cryptocurrency_symbol(), help='Cryptocurrency symbol')
def add_coin(symbol: str):
    click.echo(f"Adding {symbol.upper()} to portfolio")
"""

"""
Pytest configuration and shared fixtures for the test suite.

This module provides common fixtures and configuration for all tests
including mock objects, test data, and test environment setup.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

import pytest
from click.testing import CliRunner

from crypto_portfolio_analyzer.core.context import AppContext
from crypto_portfolio_analyzer.core.config import ConfigManager
from crypto_portfolio_analyzer.core.plugin_manager import PluginManager, BasePlugin
from crypto_portfolio_analyzer.core.events import EventBus


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Provide sample configuration data for tests."""
    return {
        "app": {
            "name": "Crypto Portfolio Analyzer",
            "version": "0.1.0",
            "debug": False
        },
        "logging": {
            "level": "INFO",
            "structured": True,
            "sampling_rate": 0.01
        },
        "plugins": {
            "directory": "plugins",
            "hot_reload": True,
            "auto_discover": True
        },
        "cache": {
            "enabled": True,
            "ttl": 300,
            "backend": "memory"
        }
    }


@pytest.fixture
def app_context(sample_config):
    """Create an application context for testing."""
    context = AppContext(
        config=sample_config,
        debug=True,
        verbose=True
    )
    return context


@pytest.fixture
async def config_manager(temp_dir, sample_config):
    """Create a configured ConfigManager for testing."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    
    # Create default config file
    default_config_file = config_dir / "default.yaml"
    import yaml
    with open(default_config_file, 'w') as f:
        yaml.dump(sample_config, f)
    
    manager = ConfigManager(config_dir=config_dir)
    await manager.initialize()
    return manager


@pytest.fixture
async def event_bus():
    """Create an event bus for testing."""
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
async def plugin_manager(temp_dir):
    """Create a plugin manager for testing."""
    plugins_dir = temp_dir / "plugins"
    plugins_dir.mkdir()
    
    manager = PluginManager(plugins_dir=plugins_dir, enable_hot_reload=False)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def mock_plugin():
    """Create a mock plugin for testing."""
    class MockPlugin(BasePlugin):
        def __init__(self, name="mock_plugin"):
            super().__init__(name)
            self.initialize_called = False
            self.teardown_called = False
            self.command_events = []
        
        async def initialize(self):
            self.initialize_called = True
        
        async def teardown(self):
            self.teardown_called = True
        
        async def on_command_start(self, command_name: str, context: Dict[str, Any]):
            self.command_events.append(("start", command_name, context))
        
        async def on_command_end(self, command_name: str, context: Dict[str, Any], result: Any):
            self.command_events.append(("end", command_name, context, result))
        
        async def on_command_error(self, command_name: str, context: Dict[str, Any], error: Exception):
            self.command_events.append(("error", command_name, context, error))
    
    return MockPlugin()


@pytest.fixture
def failing_plugin():
    """Create a plugin that fails during initialization."""
    class FailingPlugin(BasePlugin):
        def __init__(self, name="failing_plugin"):
            super().__init__(name)
        
        async def initialize(self):
            raise RuntimeError("Plugin initialization failed")
        
        async def teardown(self):
            pass
    
    return FailingPlugin()


@pytest.fixture
def sample_portfolio_data():
    """Provide sample portfolio data for testing."""
    return {
        "holdings": {
            "BTC": {
                "amount": 0.5,
                "avg_price": 30000,
                "current_price": 32000
            },
            "ETH": {
                "amount": 2.0,
                "avg_price": 1600,
                "current_price": 1700
            },
            "ADA": {
                "amount": 1000,
                "avg_price": 0.45,
                "current_price": 0.50
            }
        },
        "total_value": 19900.0,
        "last_update": "2023-01-01T00:00:00Z"
    }


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response for API testing."""
    class MockResponse:
        def __init__(self, json_data, status_code=200, headers=None):
            self.json_data = json_data
            self.status_code = status_code
            self.headers = headers or {}
        
        def json(self):
            return self.json_data
        
        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")
    
    return MockResponse


@pytest.fixture
def crypto_symbols_response(mock_http_response):
    """Mock response for cryptocurrency symbols API."""
    symbols_data = [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
        {"id": "cardano", "symbol": "ada", "name": "Cardano"},
        {"id": "polkadot", "symbol": "dot", "name": "Polkadot"},
        {"id": "chainlink", "symbol": "link", "name": "Chainlink"}
    ]
    return mock_http_response(symbols_data)


@pytest.fixture
def mock_requests(monkeypatch, crypto_symbols_response):
    """Mock requests module for HTTP testing."""
    def mock_get(url, **kwargs):
        if "coingecko.com/api/v3/coins/list" in url:
            return crypto_symbols_response
        else:
            return mock_http_response({"error": "Not found"}, 404)
    
    monkeypatch.setattr("requests.get", mock_get)


@pytest.fixture
def sample_secrets():
    """Provide sample encrypted secrets for testing."""
    return {
        "api_key": "test_api_key_12345",
        "secret_key": "test_secret_key_67890",
        "database_password": "super_secure_password"
    }


@pytest.fixture
def mock_kms_client():
    """Mock AWS KMS client for testing."""
    class MockKMSClient:
        def generate_data_key(self, KeyId, KeySpec):
            return {
                "Plaintext": b"test_encryption_key_32_bytes_long",
                "CiphertextBlob": b"encrypted_key_data"
            }
    
    return MockKMSClient()


@pytest.fixture
def test_plugin_file(temp_dir):
    """Create a test plugin file."""
    plugins_dir = temp_dir / "plugins"
    plugins_dir.mkdir()
    
    plugin_content = '''
"""Test plugin for unit testing."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class TestPlugin(BasePlugin):
    """A simple test plugin."""
    
    def __init__(self, name="test_plugin"):
        super().__init__(name)
        self.test_data = "initialized"
    
    async def initialize(self):
        self.test_data = "ready"
    
    async def teardown(self):
        self.test_data = "shutdown"
'''
    
    plugin_file = plugins_dir / "test_plugin.py"
    plugin_file.write_text(plugin_content)
    
    return plugin_file


@pytest.fixture
def invalid_plugin_file(temp_dir):
    """Create an invalid plugin file that will fail to load."""
    plugins_dir = temp_dir / "plugins"
    plugins_dir.mkdir()
    
    # Plugin with syntax error
    plugin_content = '''
"""Invalid plugin for testing error handling."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class InvalidPlugin(BasePlugin):
    def __init__(self, name="invalid_plugin"):
        super().__init__(name)
    
    async def initialize(self):
        # Syntax error - missing closing quote
        raise SyntaxError("This is a syntax error
    
    async def teardown(self):
        pass
'''
    
    plugin_file = plugins_dir / "invalid_plugin.py"
    plugin_file.write_text(plugin_content)
    
    return plugin_file


@pytest.fixture
def mock_sentry(monkeypatch):
    """Mock Sentry SDK for testing error reporting."""
    mock_sentry_sdk = Mock()
    mock_sentry_sdk.init = Mock()
    mock_sentry_sdk.capture_exception = Mock()
    mock_sentry_sdk.capture_message = Mock()
    mock_sentry_sdk.configure_scope = Mock()
    
    monkeypatch.setattr("crypto_portfolio_analyzer.core.logging.sentry_sdk", mock_sentry_sdk)
    return mock_sentry_sdk


@pytest.fixture
def sample_log_records():
    """Provide sample log records for testing."""
    import logging
    
    records = []
    
    # Create different types of log records
    logger = logging.getLogger("test_logger")
    
    # Info record
    info_record = logger.makeRecord(
        "test_logger", logging.INFO, __file__, 100,
        "Test info message", (), None
    )
    records.append(info_record)
    
    # Error record with exception
    try:
        raise ValueError("Test exception")
    except ValueError:
        error_record = logger.makeRecord(
            "test_logger", logging.ERROR, __file__, 200,
            "Test error message", (), sys.exc_info()
        )
        records.append(error_record)
    
    # Debug record
    debug_record = logger.makeRecord(
        "test_logger", logging.DEBUG, __file__, 300,
        "Test debug message", (), None
    )
    records.append(debug_record)
    
    return records


# Async test utilities
@pytest.fixture
def async_mock():
    """Create an AsyncMock for testing async functions."""
    return AsyncMock()


# Performance testing fixtures
@pytest.fixture
def benchmark_data():
    """Provide data for performance benchmarks."""
    return {
        "small_portfolio": {
            "holdings": 10,
            "transactions": 100
        },
        "medium_portfolio": {
            "holdings": 50,
            "transactions": 1000
        },
        "large_portfolio": {
            "holdings": 200,
            "transactions": 10000
        }
    }


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.asyncio = pytest.mark.asyncio

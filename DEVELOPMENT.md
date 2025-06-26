# Development Guide

This guide provides detailed instructions for setting up and working with the Crypto Portfolio Analyzer development environment.

## Development Environment Setup

### 1. Local KMS Emulator

For development and testing without AWS KMS:

#### Option A: LocalStack (Recommended)

```bash
# Install LocalStack
pip install localstack

# Start LocalStack with KMS service
localstack start -d

# Verify KMS is running
aws --endpoint-url=http://localhost:4566 kms list-keys

# Configure application to use LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export CRYPTO_PORTFOLIO_SECURITY_KMS_ENABLED=true
export CRYPTO_PORTFOLIO_SECURITY_KMS_KEY_ID=test-key-id
```

#### Option B: Local Encryption (Default)

```bash
# Use local encryption (no KMS required)
export CRYPTO_PORTFOLIO_SECURITY_KMS_ENABLED=false

# Application will automatically use local Fernet encryption
# Keys are stored in crypto_portfolio_analyzer/config/.secret_key
```

### 2. Test Secrets Injection

#### Setting Up Test Secrets

```bash
# Method 1: Using CLI commands
crypto-portfolio config secrets --set coingecko_api_key "test_coingecko_key_12345"
crypto-portfolio config secrets --set coinmarketcap_api_key "test_cmc_key_67890"
crypto-portfolio config secrets --set binance_api_key "test_binance_key"
crypto-portfolio config secrets --set binance_secret_key "test_binance_secret"
crypto-portfolio config secrets --set database_password "test_db_password"

# Method 2: Using environment variables (for CI/CD)
export CRYPTO_PORTFOLIO_SECRETS_COINGECKO_API_KEY="test_key"
export CRYPTO_PORTFOLIO_SECRETS_DATABASE_PASSWORD="test_password"
```

#### Verifying Secret Encryption

```bash
# List secret keys (values are hidden)
crypto-portfolio config secrets --list

# Check encrypted file exists
ls -la crypto_portfolio_analyzer/config/secrets.enc

# Verify encryption key
ls -la crypto_portfolio_analyzer/config/.secret_key

# Test secret retrieval
crypto-portfolio config secrets --get coingecko_api_key
```

#### Secret Rotation Testing

```bash
# Force key rotation (for testing 30-day rotation)
python -c "
import asyncio
from crypto_portfolio_analyzer.core.config import SecretManager
from pathlib import Path

async def test_rotation():
    manager = SecretManager(Path('crypto_portfolio_analyzer/config/secrets.enc'))
    await manager.initialize()
    await manager._rotate_key()
    print('Key rotation completed')

asyncio.run(test_rotation())
"
```

### 3. Dynamic Plugin Loading

#### Creating Test Plugins

```bash
# Create plugins directory
mkdir -p plugins

# Create a simple test plugin
cat > plugins/test_analytics.py << 'EOF'
"""Test analytics plugin for development."""

import logging
from typing import Any, Dict
from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

logger = logging.getLogger(__name__)

class TestAnalyticsPlugin(BasePlugin):
    """Test plugin for analytics functionality."""
    
    __version__ = "1.0.0"
    __author__ = "Development Team"
    
    def __init__(self, name="test_analytics"):
        super().__init__(name)
        self.metrics = {}
    
    async def initialize(self):
        logger.info("Test Analytics Plugin initialized")
        self.metrics = {
            "total_value": 0.0,
            "profit_loss": 0.0,
            "best_performer": None
        }
    
    async def teardown(self):
        logger.info("Test Analytics Plugin shutting down")
        self.metrics.clear()
    
    async def on_command_start(self, command_name: str, context: Dict[str, Any]):
        if command_name.startswith('portfolio'):
            logger.info(f"Analytics tracking: {command_name}")
    
    def calculate_metrics(self, portfolio_data):
        """Calculate portfolio metrics."""
        # Placeholder implementation
        return {
            "total_value": sum(holding.get("value", 0) for holding in portfolio_data.values()),
            "holdings_count": len(portfolio_data)
        }
EOF

# Create a failing plugin for error testing
cat > plugins/failing_plugin.py << 'EOF'
"""Failing plugin for error handling testing."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class FailingPlugin(BasePlugin):
    """Plugin that fails during initialization."""
    
    def __init__(self, name="failing_plugin"):
        super().__init__(name)
    
    async def initialize(self):
        raise RuntimeError("This plugin always fails to initialize")
    
    async def teardown(self):
        pass
EOF
```

#### Testing Hot-Reload

```bash
# Terminal 1: Start application with hot-reload
crypto-portfolio --debug --verbose plugins

# Terminal 2: Modify plugin and watch reload
echo '# Modified at $(date)' >> plugins/test_analytics.py

# Check logs in Terminal 1 for reload messages
```

#### Plugin Development Workflow

```bash
# 1. Create plugin stub
cat > plugins/my_new_plugin.py << 'EOF'
from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class MyNewPlugin(BasePlugin):
    async def initialize(self):
        print(f"Loading {self.name}")
    
    async def teardown(self):
        print(f"Unloading {self.name}")
EOF

# 2. Test plugin loading
crypto-portfolio plugins

# 3. Debug plugin in REPL
crypto-portfolio --debug debug-repl
# In REPL:
# plugin = plugin_manager.get_plugin('my_new_plugin')
# print(plugin.get_info())

# 4. Test plugin events
crypto-portfolio portfolio status  # Should trigger plugin events
```

#### Advanced Plugin Features

```bash
# Create plugin with entry point registration
cat > plugins/advanced_plugin.py << 'EOF'
"""Advanced plugin with entry point registration."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin
from crypto_portfolio_analyzer.core.events import EventType

class AdvancedPlugin(BasePlugin):
    """Advanced plugin demonstrating all features."""
    
    __version__ = "2.0.0"
    __author__ = "Advanced Developer"
    
    def __init__(self, name="advanced_plugin"):
        super().__init__(name)
        self.command_count = 0
    
    async def initialize(self):
        # Subscribe to additional events
        from crypto_portfolio_analyzer.core.events import get_event_bus
        event_bus = get_event_bus()
        event_bus.subscribe(EventType.CONFIG_CHANGED, self.on_config_changed)
    
    async def teardown(self):
        print(f"Processed {self.command_count} commands")
    
    async def on_command_start(self, command_name: str, context):
        self.command_count += 1
        print(f"Command #{self.command_count}: {command_name}")
    
    async def on_config_changed(self, event):
        print(f"Configuration changed: {event.data}")
EOF
```

## Testing Development Features

### 1. Plugin Error Handling

```bash
# Test plugin loading with errors
crypto-portfolio --debug plugins

# Check that good plugins load despite bad ones
ls plugins/
crypto-portfolio plugins | grep -E "(✓|✗)"
```

### 2. Configuration System

```bash
# Test configuration hierarchy
crypto-portfolio config show --format yaml

# Test environment overrides
CRYPTO_PORTFOLIO_APP_DEBUG=true crypto-portfolio config get app.debug

# Test configuration validation
crypto-portfolio config validate
```

### 3. Event System

```bash
# Test event publishing in debug REPL
crypto-portfolio --debug debug-repl

# In REPL:
# await event_bus.publish_event(EventType.CUSTOM, "test", {"data": "test"})
# print(event_bus.get_stats())
```

### 4. Logging System

```bash
# Test structured logging
CRYPTO_PORTFOLIO_LOGGING_STRUCTURED=true crypto-portfolio --debug portfolio status

# Test log sampling
CRYPTO_PORTFOLIO_LOGGING_SAMPLING_RATE=1.0 crypto-portfolio --debug portfolio status

# Test Sentry integration (requires DSN)
CRYPTO_PORTFOLIO_LOGGING_SENTRY_ENABLED=true \
CRYPTO_PORTFOLIO_LOGGING_SENTRY_DSN="your-sentry-dsn" \
crypto-portfolio portfolio status
```

## Development Tools

### 1. Code Quality

```bash
# Run all quality checks
pre-commit run --all-files

# Individual tools
flake8 crypto_portfolio_analyzer
mypy crypto_portfolio_analyzer --strict
bandit -r crypto_portfolio_analyzer
black --check crypto_portfolio_analyzer
isort --check-only crypto_portfolio_analyzer
```

### 2. Testing

```bash
# Run specific test categories
pytest tests/unit/test_plugin_manager.py::TestPluginErrorHandling::test_plugin_error_on_import_trapped_and_logged -v

# Test with coverage
pytest --cov=crypto_portfolio_analyzer --cov-report=term-missing

# Test async components
pytest -k "async" -v

# Performance testing
pytest tests/benchmarks/ --benchmark-only
```

### 3. Documentation

```bash
# Generate API documentation
python -m pydoc crypto_portfolio_analyzer.core.plugin_manager

# Test README examples
python -c "
import subprocess
import sys

# Test CLI examples from README
commands = [
    ['crypto-portfolio', '--help'],
    ['crypto-portfolio', 'version'],
    ['crypto-portfolio', 'plugins'],
]

for cmd in commands:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f'✓ {\" \".join(cmd)}')
    except Exception as e:
        print(f'✗ {\" \".join(cmd)}: {e}')
"
```

## Debugging Tips

### 1. Plugin Issues

```bash
# Check plugin syntax
python -m py_compile plugins/my_plugin.py

# Debug plugin loading
crypto-portfolio --debug plugins 2>&1 | grep -E "(ERROR|WARNING|Failed)"

# Inspect plugin in REPL
crypto-portfolio --debug debug-repl
# plugin_manager.get_all_plugins()
# plugin_manager.list_plugins()
```

### 2. Configuration Issues

```bash
# Debug configuration loading
crypto-portfolio --debug config show 2>&1 | head -20

# Check configuration file syntax
python -c "import yaml; yaml.safe_load(open('crypto_portfolio_analyzer/config/default.yaml'))"

# Verify environment variables
env | grep CRYPTO_PORTFOLIO
```

### 3. Secret Management Issues

```bash
# Reset secrets completely
rm -f crypto_portfolio_analyzer/config/secrets.enc
rm -f crypto_portfolio_analyzer/config/.secret_key

# Test secret encryption manually
python -c "
import asyncio
from crypto_portfolio_analyzer.core.config import SecretManager
from pathlib import Path

async def test():
    manager = SecretManager(Path('test_secrets.enc'))
    await manager.initialize()
    await manager.set_secret('test', 'value')
    value = await manager.get_secret('test')
    print(f'Secret test: {value}')

asyncio.run(test())
"
```

## Performance Monitoring

### 1. Plugin Loading Performance

```bash
# Time plugin loading
time crypto-portfolio plugins

# Profile plugin loading
python -m cProfile -o plugin_profile.prof -c "
import asyncio
from crypto_portfolio_analyzer.core.plugin_manager import PluginManager
from pathlib import Path

async def profile_plugins():
    manager = PluginManager(Path('plugins'))
    await manager.start()
    await manager.stop()

asyncio.run(profile_plugins())
"
```

### 2. Event System Performance

```bash
# Benchmark event publishing
python -c "
import asyncio
import time
from crypto_portfolio_analyzer.core.events import EventBus, EventType

async def benchmark():
    bus = EventBus()
    await bus.start()
    
    start = time.time()
    for i in range(1000):
        await bus.publish_event(EventType.CUSTOM, 'test', {'i': i})
    
    await asyncio.sleep(0.1)  # Wait for processing
    end = time.time()
    
    stats = bus.get_stats()
    print(f'Published 1000 events in {end-start:.3f}s')
    print(f'Stats: {stats}')
    
    await bus.stop()

asyncio.run(benchmark())
"
```

This development guide provides comprehensive instructions for working with all the advanced features implemented in Feature 1 of the Crypto Portfolio Analyzer.

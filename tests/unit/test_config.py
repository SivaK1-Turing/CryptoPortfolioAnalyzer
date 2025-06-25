"""
Unit tests for the configuration management system.

Tests configuration loading, environment overrides, secret management,
and AWS KMS integration.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest
import yaml

from crypto_portfolio_analyzer.core.config import ConfigManager, SecretManager, ConfigError


class TestSecretManager:
    """Test the SecretManager class."""
    
    @pytest.mark.asyncio
    async def test_local_encryption_initialization(self, temp_dir):
        """Test initialization with local encryption."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        
        await manager.initialize()
        
        assert manager._fernet is not None
        assert manager._use_local_encryption is True
        assert manager._key_created_at is not None
    
    @pytest.mark.asyncio
    async def test_kms_encryption_initialization(self, temp_dir, mock_kms_client):
        """Test initialization with KMS encryption."""
        secrets_file = temp_dir / "secrets.enc"
        
        with patch('boto3.client', return_value=mock_kms_client):
            manager = SecretManager(secrets_file, kms_key_id="test-key-id")
            await manager.initialize()
            
            assert manager._fernet is not None
            assert manager._use_local_encryption is False
    
    @pytest.mark.asyncio
    async def test_kms_fallback_to_local(self, temp_dir):
        """Test fallback to local encryption when KMS fails."""
        secrets_file = temp_dir / "secrets.enc"
        
        with patch('boto3.client', side_effect=Exception("KMS not available")):
            manager = SecretManager(secrets_file, kms_key_id="test-key-id")
            await manager.initialize()
            
            # Should fall back to local encryption
            assert manager._use_local_encryption is True
            assert manager._fernet is not None
    
    @pytest.mark.asyncio
    async def test_save_and_load_secrets(self, temp_dir, sample_secrets):
        """Test saving and loading secrets."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        await manager.initialize()
        
        # Save secrets
        await manager.save_secrets(sample_secrets)
        assert secrets_file.exists()
        
        # Load secrets
        loaded_secrets = await manager.load_secrets()
        assert loaded_secrets == sample_secrets
    
    @pytest.mark.asyncio
    async def test_individual_secret_operations(self, temp_dir):
        """Test individual secret get/set/delete operations."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        await manager.initialize()
        
        # Set a secret
        await manager.set_secret("test_key", "test_value")
        
        # Get the secret
        value = await manager.get_secret("test_key")
        assert value == "test_value"
        
        # Delete the secret
        deleted = await manager.delete_secret("test_key")
        assert deleted is True
        
        # Try to get deleted secret
        value = await manager.get_secret("test_key")
        assert value is None
        
        # Try to delete non-existent secret
        deleted = await manager.delete_secret("non_existent")
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_key_rotation_needed(self, temp_dir):
        """Test key rotation detection."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        
        # Mock old key creation time
        from datetime import datetime, timedelta
        manager._key_created_at = datetime.now() - timedelta(days=31)
        
        assert manager._should_rotate_key() is True
        
        # Mock recent key creation time
        manager._key_created_at = datetime.now() - timedelta(days=1)
        assert manager._should_rotate_key() is False
    
    @pytest.mark.asyncio
    async def test_key_rotation(self, temp_dir):
        """Test key rotation process."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        await manager.initialize()
        
        # Save some secrets
        original_secrets = {"key1": "value1", "key2": "value2"}
        await manager.save_secrets(original_secrets)
        
        # Force key rotation
        old_key_time = manager._key_created_at

        # Add a small delay to ensure timestamp difference
        import time
        time.sleep(0.01)

        await manager._rotate_key()

        # Verify key was rotated
        assert manager._key_created_at > old_key_time
        
        # Verify secrets are still accessible
        loaded_secrets = await manager.load_secrets()
        assert loaded_secrets == original_secrets
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_secrets_file(self, temp_dir):
        """Test loading from non-existent secrets file."""
        secrets_file = temp_dir / "nonexistent.enc"
        manager = SecretManager(secrets_file)
        await manager.initialize()
        
        secrets = await manager.load_secrets()
        assert secrets == {}
    
    @pytest.mark.asyncio
    async def test_corrupted_secrets_file(self, temp_dir):
        """Test handling of corrupted secrets file."""
        secrets_file = temp_dir / "secrets.enc"
        manager = SecretManager(secrets_file)
        await manager.initialize()
        
        # Write corrupted data
        with open(secrets_file, 'wb') as f:
            f.write(b"corrupted data")
        
        # Should return empty dict on corruption
        secrets = await manager.load_secrets()
        assert secrets == {}


class TestConfigManager:
    """Test the ConfigManager class."""
    
    @pytest.mark.asyncio
    async def test_config_manager_initialization(self, temp_dir, sample_config):
        """Test config manager initialization."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create default config file
        default_config = config_dir / "default.yaml"
        with open(default_config, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_dir=config_dir)
        await manager.initialize()
        
        assert manager._loaded is True
        assert manager.get("app.name") == "Crypto Portfolio Analyzer"
    
    @pytest.mark.asyncio
    async def test_yaml_config_loading(self, temp_dir, sample_config):
        """Test loading YAML configuration files."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create multiple config files
        default_config = config_dir / "default.yaml"
        with open(default_config, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Override config
        override_config = {
            "app": {"debug": True},
            "logging": {"level": "DEBUG"}
        }
        config_file = config_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(override_config, f)
        
        manager = ConfigManager(config_dir=config_dir)
        await manager.initialize()
        
        # Should merge configurations
        assert manager.get("app.name") == "Crypto Portfolio Analyzer"  # From default
        assert manager.get("app.debug") is True  # From override
        assert manager.get("logging.level") == "DEBUG"  # From override
    
    @pytest.mark.asyncio
    async def test_environment_overrides(self, temp_dir, sample_config):
        """Test environment variable overrides."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create default config
        default_config = config_dir / "default.yaml"
        with open(default_config, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Set environment variables
        env_vars = {
            "CRYPTO_PORTFOLIO_APP_DEBUG": "true",
            "CRYPTO_PORTFOLIO_LOGGING_LEVEL": "ERROR",
            "CRYPTO_PORTFOLIO_CACHE_TTL": "600"
        }
        
        with patch.dict(os.environ, env_vars):
            manager = ConfigManager(config_dir=config_dir)
            await manager.initialize()
            
            assert manager.get("app.debug") is True
            assert manager.get("logging.level") == "ERROR"
            assert manager.get("cache.ttl") == 600
    
    @pytest.mark.asyncio
    async def test_environment_specific_config(self, temp_dir, sample_config):
        """Test environment-specific configuration loading."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create default config
        default_config = config_dir / "default.yaml"
        with open(default_config, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Create development config
        dev_config = {"app": {"debug": True}, "logging": {"level": "DEBUG"}}
        dev_config_file = config_dir / "development.yaml"
        with open(dev_config_file, 'w') as f:
            yaml.dump(dev_config, f)
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            manager = ConfigManager(config_dir=config_dir)
            await manager.initialize()
            
            assert manager.get("app.debug") is True
            assert manager.get("logging.level") == "DEBUG"
    
    @pytest.mark.asyncio
    async def test_secrets_loading(self, temp_dir, sample_config, sample_secrets):
        """Test loading encrypted secrets."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create default config
        default_config = config_dir / "default.yaml"
        with open(default_config, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Create secrets file
        secrets_file = config_dir / "secrets.enc"
        secret_manager = SecretManager(secrets_file)
        await secret_manager.initialize()
        await secret_manager.save_secrets(sample_secrets)
        
        manager = ConfigManager(config_dir=config_dir, secrets_file=secrets_file)
        await manager.initialize()
        
        # Secrets should be loaded
        assert "secrets" in manager._config
        assert manager._config["secrets"] == sample_secrets
    
    def test_get_config_values(self, sample_config):
        """Test getting configuration values."""
        manager = ConfigManager()
        manager._config = sample_config
        manager._loaded = True
        
        # Test simple get
        assert manager.get("app.name") == "Crypto Portfolio Analyzer"
        
        # Test with default
        assert manager.get("nonexistent.key", "default") == "default"
        
        # Test nested get
        assert manager.get("logging.level") == "INFO"
        
        # Test get without loading
        manager._loaded = False
        with pytest.raises(ConfigError):
            manager.get("app.name")
    
    def test_set_config_values(self, sample_config):
        """Test setting configuration values."""
        manager = ConfigManager()
        manager._config = sample_config.copy()
        manager._loaded = True

        # Test simple set
        manager.set("app.debug", True)
        assert manager.get("app.debug") is True
        
        # Test nested set
        manager.set("new.nested.key", "value")
        assert manager.get("new.nested.key") == "value"
    
    def test_has_config_key(self, sample_config):
        """Test checking if configuration key exists."""
        manager = ConfigManager()
        manager._config = sample_config
        manager._loaded = True
        
        assert manager.has("app.name") is True
        assert manager.has("nonexistent.key") is False
    
    def test_get_all_config(self, sample_config):
        """Test getting all configuration."""
        manager = ConfigManager()
        manager._config = sample_config.copy()
        manager._config["secrets"] = {"secret_key": "secret_value"}
        
        all_config = manager.get_all()
        
        # Should exclude secrets
        assert "secrets" not in all_config
        assert "app" in all_config
        assert "logging" in all_config
    
    def test_value_conversion(self):
        """Test automatic value type conversion."""
        manager = ConfigManager()
        
        # Test boolean conversion
        assert manager._convert_value("true") is True
        assert manager._convert_value("false") is False
        assert manager._convert_value("True") is True
        
        # Test integer conversion
        assert manager._convert_value("123") == 123
        
        # Test float conversion
        assert manager._convert_value("123.45") == 123.45
        
        # Test string (no conversion)
        assert manager._convert_value("hello") == "hello"
    
    def test_config_merging(self):
        """Test configuration dictionary merging."""
        manager = ConfigManager()
        
        target = {
            "app": {"name": "Test", "version": "1.0"},
            "logging": {"level": "INFO"}
        }
        
        source = {
            "app": {"debug": True, "version": "2.0"},
            "cache": {"enabled": True}
        }
        
        manager._merge_config(target, source)
        
        # Should merge nested dictionaries
        assert target["app"]["name"] == "Test"  # Preserved
        assert target["app"]["debug"] is True  # Added
        assert target["app"]["version"] == "2.0"  # Overridden
        assert target["cache"]["enabled"] is True  # Added
    
    @pytest.mark.asyncio
    async def test_secret_operations(self, temp_dir):
        """Test secret management operations."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        manager = ConfigManager(config_dir=config_dir)
        await manager.initialize()
        
        # Set a secret
        await manager.set_secret("test_secret", "secret_value")
        
        # Get the secret
        value = await manager.get_secret("test_secret")
        assert value == "secret_value"
    
    @pytest.mark.asyncio
    async def test_invalid_yaml_handling(self, temp_dir):
        """Test handling of invalid YAML files."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # Create invalid YAML file
        invalid_config = config_dir / "default.yaml"
        with open(invalid_config, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        manager = ConfigManager(config_dir=config_dir)
        
        # Should handle invalid YAML gracefully
        await manager.initialize()
        
        # Should have empty config
        assert len(manager._config) == 0
    
    @pytest.mark.asyncio
    async def test_missing_config_directory(self, temp_dir):
        """Test handling of missing configuration directory."""
        nonexistent_dir = temp_dir / "nonexistent"
        
        manager = ConfigManager(config_dir=nonexistent_dir)
        
        # Should handle missing directory gracefully
        await manager.initialize()
        
        assert manager._loaded is True

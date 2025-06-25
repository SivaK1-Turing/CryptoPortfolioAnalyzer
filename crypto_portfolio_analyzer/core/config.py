"""
Two-tier configuration system with YAML defaults, environment overrides, and encrypted secrets.

This module provides a comprehensive configuration management system that supports
hierarchical configuration loading, environment variable overrides, and secure
secret management with AWS KMS encryption and automatic key rotation.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import base64
import json

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


class SecretManager:
    """
    Manages encrypted secrets with AWS KMS backend and automatic key rotation.
    
    Provides secure storage and retrieval of sensitive configuration data
    with automatic key rotation every 30 days.
    """
    
    def __init__(self, secrets_file: Path, kms_key_id: Optional[str] = None):
        self.secrets_file = secrets_file
        self.kms_key_id = kms_key_id
        self._fernet: Optional[Fernet] = None
        self._key_created_at: Optional[datetime] = None
        self._rotation_interval = timedelta(days=30)
        
        # For development/testing, use local encryption if no KMS key
        self._use_local_encryption = kms_key_id is None
    
    async def initialize(self) -> None:
        """Initialize the secret manager."""
        if self._use_local_encryption:
            await self._initialize_local_encryption()
        else:
            await self._initialize_kms_encryption()
    
    async def _initialize_local_encryption(self) -> None:
        """Initialize local encryption for development."""
        key_file = self.secrets_file.parent / ".secret_key"
        
        if key_file.exists():
            # Load existing key
            with open(key_file, 'rb') as f:
                key_data = json.load(f)
                key = key_data['key'].encode()
                self._key_created_at = datetime.fromisoformat(key_data['created_at'])
        else:
            # Generate new key
            key = Fernet.generate_key()
            self._key_created_at = datetime.now()
            
            # Save key
            key_file.parent.mkdir(exist_ok=True)
            with open(key_file, 'w') as f:
                json.dump({
                    'key': key.decode(),
                    'created_at': self._key_created_at.isoformat()
                }, f)
            
            logger.info("Generated new local encryption key")
        
        self._fernet = Fernet(key)
        
        # Check if key rotation is needed
        if self._should_rotate_key():
            await self._rotate_key()
    
    async def _initialize_kms_encryption(self) -> None:
        """Initialize AWS KMS encryption."""
        try:
            import boto3
            
            self.kms_client = boto3.client('kms')
            
            # Generate or retrieve data key
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'
            )
            
            key = response['Plaintext']
            self._fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
            self._key_created_at = datetime.now()
            
            logger.info("Initialized KMS encryption")
            
        except ImportError:
            logger.warning("boto3 not available, falling back to local encryption")
            self._use_local_encryption = True
            await self._initialize_local_encryption()
        except Exception as e:
            logger.error(f"Failed to initialize KMS encryption: {e}")
            self._use_local_encryption = True
            await self._initialize_local_encryption()
    
    def _should_rotate_key(self) -> bool:
        """Check if key rotation is needed."""
        if self._key_created_at is None:
            return True
        
        return datetime.now() - self._key_created_at > self._rotation_interval
    
    async def _rotate_key(self) -> None:
        """Rotate the encryption key."""
        logger.info("Rotating encryption key")
        
        # Load existing secrets
        secrets = {}
        if self.secrets_file.exists():
            secrets = await self.load_secrets()
        
        # Generate new key
        if self._use_local_encryption:
            # Force generation of new key by removing existing key file
            key_file = self.secrets_file.parent / ".secret_key"
            if key_file.exists():
                key_file.unlink()
            await self._initialize_local_encryption()
        else:
            await self._initialize_kms_encryption()
        
        # Re-encrypt secrets with new key
        if secrets:
            await self.save_secrets(secrets)
        
        logger.info("Key rotation completed")
    
    async def load_secrets(self) -> Dict[str, Any]:
        """Load and decrypt secrets from file."""
        if not self.secrets_file.exists():
            return {}
        
        if self._fernet is None:
            raise ConfigError("Secret manager not initialized")
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            secrets = json.loads(decrypted_data.decode())
            
            logger.debug(f"Loaded {len(secrets)} secrets")
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            return {}
    
    async def save_secrets(self, secrets: Dict[str, Any]) -> None:
        """Encrypt and save secrets to file."""
        if self._fernet is None:
            raise ConfigError("Secret manager not initialized")
        
        try:
            # Serialize and encrypt
            data = json.dumps(secrets).encode()
            encrypted_data = self._fernet.encrypt(data)
            
            # Save to file
            self.secrets_file.parent.mkdir(exist_ok=True)
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.debug(f"Saved {len(secrets)} secrets")
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise ConfigError(f"Failed to save secrets: {e}")
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a specific secret."""
        secrets = await self.load_secrets()
        return secrets.get(key)
    
    async def set_secret(self, key: str, value: str) -> None:
        """Set a specific secret."""
        secrets = await self.load_secrets()
        secrets[key] = value
        await self.save_secrets(secrets)
    
    async def delete_secret(self, key: str) -> bool:
        """Delete a specific secret."""
        secrets = await self.load_secrets()
        if key in secrets:
            del secrets[key]
            await self.save_secrets(secrets)
            return True
        return False


class ConfigManager:
    """
    Comprehensive configuration management system.
    
    Supports hierarchical configuration loading from YAML files,
    environment variable overrides, and encrypted secret management.
    """
    
    def __init__(
        self,
        config_dir: Path = None,
        secrets_file: Path = None,
        kms_key_id: Optional[str] = None,
        env_prefix: str = "CRYPTO_PORTFOLIO"
    ):
        self.config_dir = config_dir or Path("crypto_portfolio_analyzer/config")
        self.secrets_file = secrets_file or (self.config_dir / "secrets.enc")
        self.env_prefix = env_prefix
        
        self._config: Dict[str, Any] = {}
        self._secret_manager = SecretManager(self.secrets_file, kms_key_id)
        self._loaded = False
    
    async def initialize(self) -> None:
        """Initialize the configuration manager."""
        logger.info("Initializing configuration manager")
        
        # Load environment variables
        load_dotenv()
        
        # Initialize secret manager
        await self._secret_manager.initialize()
        
        # Load configuration
        await self.load_config()
        
        self._loaded = True
        logger.info("Configuration manager initialized")
    
    async def load_config(self) -> None:
        """Load configuration from all sources."""
        # Load YAML defaults
        await self._load_yaml_config()
        
        # Apply environment overrides
        self._apply_env_overrides()
        
        # Load secrets
        await self._load_secrets()
        
        logger.info(f"Loaded configuration with {len(self._config)} top-level keys")
    
    async def _load_yaml_config(self) -> None:
        """Load configuration from YAML files."""
        config_files = [
            self.config_dir / "default.yaml",
            self.config_dir / "config.yaml",
        ]
        
        # Also check for environment-specific config
        env = os.getenv("ENVIRONMENT", "development")
        env_config = self.config_dir / f"{env}.yaml"
        if env_config.exists():
            config_files.append(env_config)
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        file_config = yaml.safe_load(f) or {}
                    
                    # Merge configuration
                    self._merge_config(self._config, file_config)
                    logger.debug(f"Loaded config from {config_file}")
                    
                except Exception as e:
                    logger.error(f"Failed to load config from {config_file}: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        prefix = f"{self.env_prefix}_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace('_', '.')
                self._set_nested_value(self._config, config_key, value)
                logger.debug(f"Applied env override: {config_key} = {value}")
    
    async def _load_secrets(self) -> None:
        """Load encrypted secrets."""
        try:
            secrets = await self._secret_manager.load_secrets()
            if secrets:
                self._config['secrets'] = secrets
                logger.debug(f"Loaded {len(secrets)} secrets")
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value
    
    def _set_nested_value(self, config: Dict[str, Any], key_path: str, value: str) -> None:
        """Set a nested configuration value using dot notation."""
        keys = key_path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Try to convert value to appropriate type
        final_value = self._convert_value(value)
        current[keys[-1]] = final_value
    
    def _convert_value(self, value: Any) -> Any:
        """Convert string value to appropriate type."""
        # If not a string, return as-is
        if not isinstance(value, str):
            return value

        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'

        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass

        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        if not self._loaded:
            raise ConfigError("Configuration not loaded")
        
        keys = key.split('.')
        current = self._config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation."""
        self._set_nested_value(self._config, key, value)
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        return await self._secret_manager.get_secret(key)
    
    async def set_secret(self, key: str, value: str) -> None:
        """Set a secret value."""
        await self._secret_manager.set_secret(key, value)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration (excluding secrets)."""
        config = self._config.copy()
        config.pop('secrets', None)  # Remove secrets from general config
        return config
    
    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""
        if not self._loaded:
            return False

        keys = key.split('.')
        current = self._config

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return False

        return True

"""
Configuration management plugin.

This plugin provides enhanced configuration management capabilities including
configuration validation, environment-specific settings, and configuration
change notifications.
"""

import logging
from typing import Any, Dict

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin
from crypto_portfolio_analyzer.core.events import EventType

logger = logging.getLogger(__name__)


class ConfigPlugin(BasePlugin):
    """
    Configuration management plugin.
    
    Provides enhanced configuration management including validation,
    change tracking, and environment-specific configuration handling.
    """
    
    __version__ = "1.0.0"
    __author__ = "Crypto Portfolio Analyzer Team"
    
    def __init__(self, name: str = "config"):
        super().__init__(name)
        self.config_schema = {}
        self.config_history = []
        self.validation_rules = {}
    
    async def initialize(self) -> None:
        """Initialize the configuration plugin."""
        logger.info("Initializing configuration plugin")
        
        # Load configuration schema and validation rules
        await self._load_config_schema()
        await self._setup_validation_rules()
        
        logger.info("Configuration plugin initialized")
    
    async def teardown(self) -> None:
        """Clean up the configuration plugin."""
        logger.info("Shutting down configuration plugin")
        
        # Save configuration history
        await self._save_config_history()
        
        logger.info("Configuration plugin shutdown complete")
    
    async def _load_config_schema(self) -> None:
        """Load configuration schema for validation."""
        # In a real implementation, this would load from a JSON schema file
        self.config_schema = {
            "app": {
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "debug": {"type": "boolean"}
                }
            },
            "logging": {
                "type": "object",
                "required": ["level"],
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    },
                    "format": {"type": "string"},
                    "structured": {"type": "boolean"}
                }
            },
            "plugins": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string"},
                    "hot_reload": {"type": "boolean"},
                    "auto_discover": {"type": "boolean"}
                }
            }
        }
        
        logger.debug("Loaded configuration schema")
    
    async def _setup_validation_rules(self) -> None:
        """Set up configuration validation rules."""
        self.validation_rules = {
            "app.name": lambda x: isinstance(x, str) and len(x) > 0,
            "app.version": lambda x: isinstance(x, str) and len(x) > 0,
            "logging.level": lambda x: x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "plugins.directory": lambda x: isinstance(x, str) and len(x) > 0,
        }
        
        logger.debug(f"Set up {len(self.validation_rules)} validation rules")
    
    async def _save_config_history(self) -> None:
        """Save configuration change history."""
        # In a real implementation, this would save to a file or database
        logger.debug(f"Saved configuration history: {len(self.config_history)} changes")
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate configuration against schema and rules.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Dictionary of validation errors (empty if valid)
        """
        errors = {}
        
        # Validate against schema
        for section, schema in self.config_schema.items():
            if section not in config:
                if schema.get("required"):
                    errors[section] = f"Required section '{section}' is missing"
                continue
            
            section_config = config[section]
            section_errors = self._validate_section(section_config, schema, section)
            errors.update(section_errors)
        
        # Validate against custom rules
        for rule_key, rule_func in self.validation_rules.items():
            try:
                value = self._get_nested_value(config, rule_key)
                if value is not None and not rule_func(value):
                    errors[rule_key] = f"Validation failed for {rule_key}"
            except KeyError:
                # Key doesn't exist, skip validation
                pass
        
        return errors
    
    def _validate_section(self, section_config: Dict[str, Any], schema: Dict[str, Any], section_name: str) -> Dict[str, str]:
        """Validate a configuration section against its schema."""
        errors = {}
        
        # Check required properties
        required = schema.get("required", [])
        for prop in required:
            if prop not in section_config:
                errors[f"{section_name}.{prop}"] = f"Required property '{prop}' is missing"
        
        # Validate properties
        properties = schema.get("properties", {})
        for prop, prop_schema in properties.items():
            if prop not in section_config:
                continue
            
            value = section_config[prop]
            prop_errors = self._validate_property(value, prop_schema, f"{section_name}.{prop}")
            errors.update(prop_errors)
        
        return errors
    
    def _validate_property(self, value: Any, schema: Dict[str, Any], prop_path: str) -> Dict[str, str]:
        """Validate a single property against its schema."""
        errors = {}
        
        # Type validation
        expected_type = schema.get("type")
        if expected_type:
            if expected_type == "string" and not isinstance(value, str):
                errors[prop_path] = f"Expected string, got {type(value).__name__}"
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors[prop_path] = f"Expected boolean, got {type(value).__name__}"
            elif expected_type == "object" and not isinstance(value, dict):
                errors[prop_path] = f"Expected object, got {type(value).__name__}"
        
        # Enum validation
        enum_values = schema.get("enum")
        if enum_values and value not in enum_values:
            errors[prop_path] = f"Value must be one of {enum_values}, got '{value}'"
        
        return errors
    
    def _get_nested_value(self, config: Dict[str, Any], key_path: str) -> Any:
        """Get a nested configuration value using dot notation."""
        keys = key_path.split('.')
        current = config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                raise KeyError(f"Key '{key_path}' not found")
        
        return current
    
    def track_config_change(self, key: str, old_value: Any, new_value: Any, source: str = "unknown") -> None:
        """Track a configuration change."""
        change_record = {
            "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                logger.name, logging.INFO, __file__, 0, "", (), None
            )) if logger.handlers else "unknown",
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
            "source": source
        }
        
        self.config_history.append(change_record)
        logger.info(f"Configuration changed: {key} = {new_value} (source: {source})")
    
    def get_config_history(self) -> list:
        """Get configuration change history."""
        return self.config_history.copy()
    
    def get_validation_summary(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of configuration validation."""
        errors = self.validate_config(config)
        
        return {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "errors": errors,
            "sections_validated": len(self.config_schema),
            "rules_checked": len(self.validation_rules)
        }
    
    async def on_command_start(self, command_name: str, context: Dict[str, Any]) -> None:
        """Handle command start events."""
        if command_name.startswith('config'):
            logger.debug(f"Configuration command started: {command_name}")
    
    async def on_command_end(self, command_name: str, context: Dict[str, Any], result: Any) -> None:
        """Handle command end events."""
        if command_name.startswith('config'):
            logger.debug(f"Configuration command completed: {command_name}")
    
    async def on_command_error(self, command_name: str, context: Dict[str, Any], error: Exception) -> None:
        """Handle command error events."""
        if command_name.startswith('config'):
            logger.error(f"Configuration command failed: {command_name} - {error}")
    
    def get_info(self):
        """Get plugin information."""
        info = super().get_info()
        info.description = "Enhanced configuration management and validation"
        return info

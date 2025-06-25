"""
Unit tests for the plugin manager.

Tests plugin discovery, loading, unloading, hot-reloading, and error handling
including the specific test case for plugin error simulation.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from crypto_portfolio_analyzer.core.plugin_manager import (
    PluginManager, BasePlugin, PluginInfo, PluginWatcher
)
from crypto_portfolio_analyzer.core.events import EventType


class TestBasePlugin:
    """Test the BasePlugin base class."""
    
    def test_plugin_initialization(self):
        """Test basic plugin initialization."""
        plugin = MockTestPlugin("test_plugin")
        
        assert plugin.name == "test_plugin"
        assert plugin.enabled is True
        assert plugin._initialized is False
    
    def test_plugin_info(self):
        """Test plugin info generation."""
        plugin = MockTestPlugin("test_plugin")
        info = plugin.get_info()
        
        assert isinstance(info, PluginInfo)
        assert info.name == "test_plugin"
        assert info.version == "1.0.0"
        assert info.author == "Test Author"
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin lifecycle methods."""
        plugin = MockTestPlugin("test_plugin")
        
        # Test initialization
        await plugin.initialize()
        assert plugin._initialized is True
        
        # Test teardown
        await plugin.teardown()
        assert plugin._initialized is False
    
    @pytest.mark.asyncio
    async def test_plugin_event_handlers(self):
        """Test plugin event handler methods."""
        plugin = MockTestPlugin("test_plugin")
        
        # Test command event handlers (should not raise exceptions)
        await plugin.on_command_start("test_command", {})
        await plugin.on_command_end("test_command", {}, "result")
        await plugin.on_command_error("test_command", {}, Exception("test"))


class TestPluginManager:
    """Test the PluginManager class."""
    
    @pytest.mark.asyncio
    async def test_plugin_manager_initialization(self, temp_dir):
        """Test plugin manager initialization."""
        plugins_dir = temp_dir / "plugins"
        manager = PluginManager(plugins_dir, enable_hot_reload=False)
        
        await manager.start()
        
        assert manager.plugins_dir == plugins_dir
        assert plugins_dir.exists()
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_plugin_success(self, temp_dir):
        """Test successful plugin loading."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()
        
        plugin = MockTestPlugin("test_plugin")
        await manager._load_plugin(plugin)
        
        assert "test_plugin" in manager._plugins
        assert plugin._initialized is True
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_plugin_failure(self, temp_dir):
        """Test plugin loading failure handling."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()
        
        # Create a plugin that fails during initialization
        failing_plugin = FailingTestPlugin("failing_plugin")
        
        with pytest.raises(RuntimeError, match="Plugin initialization failed"):
            await manager._load_plugin(failing_plugin)
        
        # Plugin should not be in the loaded plugins
        assert "failing_plugin" not in manager._plugins
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_unload_plugin(self, temp_dir):
        """Test plugin unloading."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()
        
        # Load a plugin first
        plugin = MockTestPlugin("test_plugin")
        await manager._load_plugin(plugin)
        
        # Unload the plugin
        await manager._unload_plugin("test_plugin")
        
        assert "test_plugin" not in manager._plugins
        assert plugin._initialized is False
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_unload_nonexistent_plugin(self, temp_dir):
        """Test unloading a plugin that doesn't exist."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()
        
        # Should not raise an exception
        await manager._unload_plugin("nonexistent_plugin")
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_plugin_from_file(self, test_plugin_file):
        """Test loading a plugin from a file."""
        plugins_dir = test_plugin_file.parent
        manager = PluginManager(plugins_dir, enable_hot_reload=False)
        await manager.start()
        
        await manager._load_plugin_from_file(test_plugin_file)
        
        # Check if plugin was loaded
        plugins = manager.get_all_plugins()
        assert len(plugins) > 0
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_invalid_plugin_file(self, invalid_plugin_file):
        """Test loading an invalid plugin file."""
        plugins_dir = invalid_plugin_file.parent
        manager = PluginManager(plugins_dir, enable_hot_reload=False)
        await manager.start()
        
        # Should handle the error gracefully
        await manager._load_plugin_from_file(invalid_plugin_file)
        
        # Only core plugins should be loaded (not the invalid one)
        plugins = manager.get_all_plugins()
        assert len(plugins) == 2  # core_config and core_portfolio
        assert 'invalid_plugin' not in plugins
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_reload_plugin_from_file(self, test_plugin_file):
        """Test reloading a plugin from a file."""
        plugins_dir = test_plugin_file.parent
        manager = PluginManager(plugins_dir, enable_hot_reload=False)
        await manager.start()
        
        # Load plugin initially
        await manager._load_plugin_from_file(test_plugin_file)
        initial_count = len(manager.get_all_plugins())
        
        # Reload the plugin
        await manager.reload_plugin_from_file(test_plugin_file)
        
        # Should still have the same number of plugins
        assert len(manager.get_all_plugins()) == initial_count
        
        await manager.stop()
    
    def test_get_plugin(self, temp_dir):
        """Test getting a specific plugin."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        
        # Add a mock plugin directly
        plugin = MockTestPlugin("test_plugin")
        manager._plugins["test_plugin"] = plugin
        
        retrieved_plugin = manager.get_plugin("test_plugin")
        assert retrieved_plugin is plugin
        
        # Test getting non-existent plugin
        assert manager.get_plugin("nonexistent") is None
    
    def test_get_all_plugins(self, temp_dir):
        """Test getting all plugins."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        
        # Add mock plugins
        plugin1 = MockTestPlugin("plugin1")
        plugin2 = MockTestPlugin("plugin2")
        manager._plugins["plugin1"] = plugin1
        manager._plugins["plugin2"] = plugin2
        
        all_plugins = manager.get_all_plugins()
        assert len(all_plugins) == 2
        assert "plugin1" in all_plugins
        assert "plugin2" in all_plugins
    
    def test_list_plugins(self, temp_dir):
        """Test listing plugin information."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        
        # Add mock plugins
        plugin1 = MockTestPlugin("plugin1")
        plugin2 = MockTestPlugin("plugin2")
        manager._plugins["plugin1"] = plugin1
        manager._plugins["plugin2"] = plugin2
        
        plugin_list = manager.list_plugins()
        assert len(plugin_list) == 2
        assert all(isinstance(info, PluginInfo) for info in plugin_list)
    
    def test_is_plugin_loaded(self, temp_dir):
        """Test checking if a plugin is loaded."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        
        # Add a mock plugin
        plugin = MockTestPlugin("test_plugin")
        manager._plugins["test_plugin"] = plugin
        
        assert manager.is_plugin_loaded("test_plugin") is True
        assert manager.is_plugin_loaded("nonexistent") is False


class TestPluginWatcher:
    """Test the PluginWatcher for hot-reloading."""
    
    def test_plugin_watcher_initialization(self, temp_dir):
        """Test plugin watcher initialization."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        watcher = PluginWatcher(manager)
        
        assert watcher.plugin_manager() is manager
        assert isinstance(watcher._reload_tasks, set)
    
    def test_is_python_file(self, temp_dir):
        """Test Python file detection."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        watcher = PluginWatcher(manager)
        
        assert watcher._is_python_file("test.py") is True
        assert watcher._is_python_file("test.txt") is False
        assert watcher._is_python_file("__pycache__/test.py") is False
    
    @pytest.mark.asyncio
    async def test_file_modification_handling(self, temp_dir, test_plugin_file):
        """Test handling of file modification events."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        watcher = PluginWatcher(manager)
        
        # Mock the event
        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(test_plugin_file))
        
        # Mock the reload method to avoid actual reloading
        with patch.object(watcher, '_schedule_reload') as mock_schedule:
            watcher.on_modified(event)
            mock_schedule.assert_called_once_with(str(test_plugin_file))
    
    @pytest.mark.asyncio
    async def test_file_creation_handling(self, temp_dir, test_plugin_file):
        """Test handling of file creation events."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        watcher = PluginWatcher(manager)
        
        # Mock the event
        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(test_plugin_file))
        
        # Mock the reload method
        with patch.object(watcher, '_schedule_reload') as mock_schedule:
            watcher.on_created(event)
            mock_schedule.assert_called_once_with(str(test_plugin_file))


class TestPluginErrorHandling:
    """Test plugin error handling scenarios as specified in the requirements."""
    
    @pytest.mark.asyncio
    async def test_plugin_error_on_import_trapped_and_logged(self, temp_dir, event_bus):
        """
        Test that CLI traps plugin import errors, logs warnings, and continues loading other plugins.
        
        This is the specific test case mentioned in the requirements:
        "simulate a plugin error on import, assert that the CLI traps it, logs a warning, 
        and continues loading other plugins."
        """
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        # Create a plugin file with import error
        bad_plugin_content = '''
"""Plugin with import error."""
import non_existent_module  # This will cause ImportError

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class BadPlugin(BasePlugin):
    async def initialize(self):
        pass
    
    async def teardown(self):
        pass
'''
        
        bad_plugin_file = plugins_dir / "bad_plugin.py"
        bad_plugin_file.write_text(bad_plugin_content)
        
        # Create a good plugin file
        good_plugin_content = '''
"""Good plugin for testing."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class GoodPlugin(BasePlugin):
    async def initialize(self):
        self.initialized = True
    
    async def teardown(self):
        pass
'''
        
        good_plugin_file = plugins_dir / "good_plugin.py"
        good_plugin_file.write_text(good_plugin_content)
        
        # Create plugin manager
        manager = PluginManager(plugins_dir, enable_hot_reload=False)
        
        # Capture log messages
        import logging
        log_messages = []
        
        class TestLogHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record.getMessage())
        
        test_handler = TestLogHandler()
        logger = logging.getLogger('crypto_portfolio_analyzer.core.plugin_manager')
        logger.addHandler(test_handler)
        logger.setLevel(logging.DEBUG)
        
        try:
            await manager.start()
            
            # Check that the good plugin was loaded despite the bad plugin failing
            loaded_plugins = manager.get_all_plugins()
            
            # Should have loaded the good plugin
            good_plugin_loaded = any(
                'GoodPlugin' in str(type(plugin)) 
                for plugin in loaded_plugins.values()
            )
            assert good_plugin_loaded, "Good plugin should be loaded despite bad plugin failure"
            
            # Check that error was logged
            error_logged = any(
                "Failed to load plugin" in msg and "bad_plugin" in msg 
                for msg in log_messages
            )
            assert error_logged, "Plugin import error should be logged"
            
            # Check that manager continued loading other plugins
            assert len(loaded_plugins) > 0, "Manager should continue loading other plugins"
            
        finally:
            logger.removeHandler(test_handler)
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_plugin_initialization_error_handling(self, temp_dir):
        """Test handling of plugin initialization errors."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()

        # Create a plugin that fails during initialization
        failing_plugin = FailingTestPlugin("failing_plugin")

        # Try to load the failing plugin - should raise RuntimeError
        with pytest.raises(RuntimeError, match="Plugin initialization failed"):
            await manager._load_plugin(failing_plugin)

        # Verify the plugin was not added to the manager
        plugins = manager.get_all_plugins()
        assert "failing_plugin" not in plugins
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_plugin_teardown_error_handling(self, temp_dir):
        """Test handling of plugin teardown errors."""
        manager = PluginManager(temp_dir / "plugins", enable_hot_reload=False)
        await manager.start()
        
        # Create a plugin that fails during teardown
        plugin = FailingTeardownPlugin("teardown_failing_plugin")
        await manager._load_plugin(plugin)
        
        # Capture log messages
        import logging
        log_messages = []
        
        class TestLogHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record.getMessage())
        
        test_handler = TestLogHandler()
        logger = logging.getLogger('crypto_portfolio_analyzer.core.plugin_manager')
        logger.addHandler(test_handler)
        
        try:
            # Unload the plugin (should handle teardown error gracefully)
            await manager._unload_plugin("teardown_failing_plugin")
            
            # Check that error was logged
            error_logged = any(
                "Error unloading plugin" in msg 
                for msg in log_messages
            )
            assert error_logged, "Plugin teardown error should be logged"
            
        finally:
            logger.removeHandler(test_handler)
            await manager.stop()


# Helper classes for testing
class MockTestPlugin(BasePlugin):
    """Mock plugin for testing."""
    
    __version__ = "1.0.0"
    __author__ = "Test Author"
    
    def __init__(self, name):
        super().__init__(name)
        self._initialized = False
    
    async def initialize(self):
        self._initialized = True
    
    async def teardown(self):
        self._initialized = False


class FailingTestPlugin(BasePlugin):
    """Plugin that fails during initialization."""
    
    def __init__(self, name):
        super().__init__(name)
    
    async def initialize(self):
        raise RuntimeError("Plugin initialization failed")
    
    async def teardown(self):
        pass


class FailingTeardownPlugin(BasePlugin):
    """Plugin that fails during teardown."""
    
    def __init__(self, name):
        super().__init__(name)
    
    async def initialize(self):
        pass
    
    async def teardown(self):
        raise RuntimeError("Plugin teardown failed")

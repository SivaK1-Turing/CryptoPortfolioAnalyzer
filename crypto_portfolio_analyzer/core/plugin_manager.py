"""
Plugin management system with hot-reloading and lifecycle management.

This module provides comprehensive plugin discovery, loading, and management
capabilities including entry point inspection, file system watching, and
plugin lifecycle events.
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass
import weakref

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from crypto_portfolio_analyzer.core.events import EventBus, EventType, get_event_bus
from crypto_portfolio_analyzer.core.context import get_current_context

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    
    name: str
    module_name: str
    version: str
    description: str
    author: str
    entry_point: Optional[str] = None
    file_path: Optional[Path] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BasePlugin(ABC):
    """
    Base class for all plugins.
    
    Plugins must inherit from this class and implement the required methods.
    The plugin lifecycle is managed by the PluginManager.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the plugin.
        
        This method is called when the plugin is loaded and should perform
        any necessary setup operations.
        """
        pass
    
    @abstractmethod
    async def teardown(self) -> None:
        """
        Clean up the plugin.
        
        This method is called when the plugin is unloaded and should perform
        any necessary cleanup operations.
        """
        pass
    
    def get_info(self) -> PluginInfo:
        """Get plugin information."""
        return PluginInfo(
            name=self.name,
            module_name=self.__class__.__module__,
            version=getattr(self, '__version__', '0.1.0'),
            description=getattr(self, '__doc__', 'No description'),
            author=getattr(self, '__author__', 'Unknown'),
        )
    
    async def on_command_start(self, command_name: str, context: Dict[str, Any]) -> None:
        """Called when a command starts execution."""
        pass
    
    async def on_command_end(self, command_name: str, context: Dict[str, Any], result: Any) -> None:
        """Called when a command completes execution."""
        pass
    
    async def on_command_error(self, command_name: str, context: Dict[str, Any], error: Exception) -> None:
        """Called when a command encounters an error."""
        pass


class PluginWatcher(FileSystemEventHandler):
    """
    File system watcher for plugin hot-reloading.
    
    Monitors the plugins directory for changes and triggers plugin reloading
    when files are modified or created.
    """
    
    def __init__(self, plugin_manager: 'PluginManager'):
        super().__init__()
        self.plugin_manager = weakref.ref(plugin_manager)
        self._reload_tasks: Set[asyncio.Task] = set()
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if self._is_python_file(event.src_path):
            logger.info(f"Plugin file modified: {event.src_path}")
            self._schedule_reload(event.src_path)
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        if self._is_python_file(event.src_path):
            logger.info(f"New plugin file created: {event.src_path}")
            self._schedule_reload(event.src_path)
    
    def _is_python_file(self, file_path: str) -> bool:
        """Check if the file is a Python file."""
        return file_path.endswith('.py') and '__pycache__' not in file_path
    
    def _schedule_reload(self, file_path: str) -> None:
        """Schedule a plugin reload."""
        manager = self.plugin_manager()
        if manager is None:
            return
        
        # Create reload task
        task = asyncio.create_task(self._reload_plugin(file_path))
        self._reload_tasks.add(task)
        
        # Clean up completed tasks
        task.add_done_callback(self._reload_tasks.discard)
    
    async def _reload_plugin(self, file_path: str) -> None:
        """Reload a plugin from file path."""
        manager = self.plugin_manager()
        if manager is None:
            return
        
        try:
            # Add a small delay to avoid reloading during file writes
            await asyncio.sleep(0.5)
            
            plugin_path = Path(file_path)
            await manager.reload_plugin_from_file(plugin_path)
            
        except Exception as e:
            logger.error(f"Failed to reload plugin from {file_path}: {e}")


class PluginManager:
    """
    Comprehensive plugin management system.
    
    Handles plugin discovery from entry points and file system, loading,
    unloading, hot-reloading, and lifecycle management.
    """
    
    def __init__(self, plugins_dir: Optional[Path] = None, enable_hot_reload: bool = True):
        self.plugins_dir = plugins_dir or Path("plugins")
        self.enable_hot_reload = enable_hot_reload
        
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._event_bus = get_event_bus()
        
        # File system watcher
        self._observer: Optional[Observer] = None
        self._watcher: Optional[PluginWatcher] = None
        
        # Plugin loading state
        self._loading_lock = asyncio.Lock()
        self._loaded_entry_points: Set[str] = set()
    
    async def start(self) -> None:
        """Start the plugin manager."""
        logger.info("Starting plugin manager")
        
        # Ensure plugins directory exists
        self.plugins_dir.mkdir(exist_ok=True)
        
        # Start file system watcher if hot reload is enabled
        if self.enable_hot_reload:
            await self._start_watcher()
        
        # Load plugins from entry points
        await self._load_entry_point_plugins()
        
        # Load plugins from file system
        await self._load_file_system_plugins()
        
        logger.info(f"Plugin manager started with {len(self._plugins)} plugins")
    
    async def stop(self) -> None:
        """Stop the plugin manager."""
        logger.info("Stopping plugin manager")
        
        # Stop file system watcher
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._watcher = None
        
        # Unload all plugins
        await self._unload_all_plugins()
        
        logger.info("Plugin manager stopped")
    
    async def _start_watcher(self) -> None:
        """Start the file system watcher."""
        if not self.plugins_dir.exists():
            return
        
        self._watcher = PluginWatcher(self)
        self._observer = Observer()
        self._observer.schedule(self._watcher, str(self.plugins_dir), recursive=True)
        self._observer.start()
        
        logger.info(f"Started watching {self.plugins_dir} for plugin changes")

    async def _load_entry_point_plugins(self) -> None:
        """Load plugins from entry points defined in pyproject.toml."""
        try:
            import pkg_resources

            for entry_point in pkg_resources.iter_entry_points('crypto_portfolio_analyzer.plugins'):
                if entry_point.name in self._loaded_entry_points:
                    continue

                try:
                    await self._event_bus.publish_event(
                        EventType.PLUGIN_LOADING,
                        "plugin_manager",
                        {"plugin_name": entry_point.name, "source": "entry_point"}
                    )

                    plugin_class = entry_point.load()
                    plugin = plugin_class(entry_point.name)

                    await self._load_plugin(plugin, entry_point=entry_point.name)
                    self._loaded_entry_points.add(entry_point.name)

                    logger.info(f"Loaded plugin from entry point: {entry_point.name}")

                except Exception as e:
                    logger.error(f"Failed to load plugin {entry_point.name}: {e}")
                    await self._event_bus.publish_event(
                        EventType.PLUGIN_FAILED,
                        "plugin_manager",
                        {"plugin_name": entry_point.name, "error": str(e)}
                    )

        except ImportError:
            logger.warning("pkg_resources not available, skipping entry point plugin loading")

    async def _load_file_system_plugins(self) -> None:
        """Load plugins from the file system."""
        if not self.plugins_dir.exists():
            return

        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue

            try:
                await self._load_plugin_from_file(plugin_file)
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_file}: {e}")

    async def _load_plugin_from_file(self, plugin_file: Path) -> None:
        """Load a plugin from a Python file."""
        module_name = f"plugins.{plugin_file.stem}"

        try:
            await self._event_bus.publish_event(
                EventType.PLUGIN_LOADING,
                "plugin_manager",
                {"plugin_name": plugin_file.stem, "source": "file_system", "file_path": str(plugin_file)}
            )

            # Load module from file
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for {plugin_file}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin classes in the module
            plugin_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BasePlugin) and
                    obj is not BasePlugin):
                    plugin_classes.append(obj)

            if not plugin_classes:
                logger.warning(f"No plugin classes found in {plugin_file}")
                return

            # Load all plugin classes from the file
            for plugin_class in plugin_classes:
                plugin_name = getattr(plugin_class, 'plugin_name', plugin_class.__name__)
                plugin = plugin_class(plugin_name)

                await self._load_plugin(plugin, file_path=plugin_file)
                self._plugin_modules[plugin_name] = module

                logger.info(f"Loaded plugin from file: {plugin_name} ({plugin_file})")

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_file}: {e}")
            await self._event_bus.publish_event(
                EventType.PLUGIN_FAILED,
                "plugin_manager",
                {"plugin_name": plugin_file.stem, "error": str(e), "file_path": str(plugin_file)}
            )

    async def _load_plugin(self, plugin: BasePlugin, entry_point: str = None, file_path: Path = None) -> None:
        """Load and initialize a plugin."""
        async with self._loading_lock:
            if plugin.name in self._plugins:
                logger.warning(f"Plugin {plugin.name} is already loaded")
                return

            try:
                # Initialize the plugin
                await plugin.initialize()
                plugin._initialized = True

                # Store the plugin
                self._plugins[plugin.name] = plugin

                # Subscribe to command events
                self._event_bus.subscribe(EventType.COMMAND_START, plugin.on_command_start)
                self._event_bus.subscribe(EventType.COMMAND_END, plugin.on_command_end)
                self._event_bus.subscribe(EventType.COMMAND_ERROR, plugin.on_command_error)

                # Publish plugin loaded event
                await self._event_bus.publish_event(
                    EventType.PLUGIN_LOADED,
                    "plugin_manager",
                    {
                        "plugin_name": plugin.name,
                        "plugin_info": plugin.get_info().__dict__,
                        "entry_point": entry_point,
                        "file_path": str(file_path) if file_path else None
                    }
                )

                logger.info(f"Successfully loaded and initialized plugin: {plugin.name}")

            except Exception as e:
                logger.error(f"Failed to initialize plugin {plugin.name}: {e}")
                await self._event_bus.publish_event(
                    EventType.PLUGIN_FAILED,
                    "plugin_manager",
                    {"plugin_name": plugin.name, "error": str(e)}
                )
                raise

    async def reload_plugin_from_file(self, plugin_file: Path) -> None:
        """Reload a plugin from a file."""
        plugin_name = plugin_file.stem

        # Unload existing plugin if it exists
        if plugin_name in self._plugins:
            await self._unload_plugin(plugin_name)

        # Remove from module cache
        if plugin_name in self._plugin_modules:
            del self._plugin_modules[plugin_name]

        # Reload the plugin
        await self._load_plugin_from_file(plugin_file)

    async def _unload_plugin(self, plugin_name: str) -> None:
        """Unload a specific plugin."""
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin {plugin_name} is not loaded")
            return

        plugin = self._plugins[plugin_name]

        try:
            await self._event_bus.publish_event(
                EventType.PLUGIN_UNLOADING,
                "plugin_manager",
                {"plugin_name": plugin_name}
            )

            # Unsubscribe from events
            self._event_bus.unsubscribe(EventType.COMMAND_START, plugin.on_command_start)
            self._event_bus.unsubscribe(EventType.COMMAND_END, plugin.on_command_end)
            self._event_bus.unsubscribe(EventType.COMMAND_ERROR, plugin.on_command_error)

            # Call teardown
            if plugin._initialized:
                await plugin.teardown()
                plugin._initialized = False

            # Remove from plugins dict
            del self._plugins[plugin_name]

            await self._event_bus.publish_event(
                EventType.PLUGIN_UNLOADED,
                "plugin_manager",
                {"plugin_name": plugin_name}
            )

            logger.info(f"Unloaded plugin: {plugin_name}")

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")

    async def _unload_all_plugins(self) -> None:
        """Unload all plugins."""
        plugin_names = list(self._plugins.keys())
        for plugin_name in plugin_names:
            await self._unload_plugin(plugin_name)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get information about a plugin."""
        plugin = self.get_plugin(name)
        return plugin.get_info() if plugin else None

    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins."""
        return [plugin.get_info() for plugin in self._plugins.values()]

    def is_plugin_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return name in self._plugins

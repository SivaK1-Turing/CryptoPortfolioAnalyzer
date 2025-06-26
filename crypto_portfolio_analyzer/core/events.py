"""
Asyncio-based event bus for plugin lifecycle and command events.

This module provides a publish-subscribe event system that allows plugins
to communicate and respond to application lifecycle events.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Union
from dataclasses import dataclass
from enum import Enum
import weakref
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types for the application."""
    
    # Plugin lifecycle events
    PLUGIN_LOADING = "plugin_loading"
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_FAILED = "plugin_failed"
    PLUGIN_UNLOADING = "plugin_unloading"
    PLUGIN_UNLOADED = "plugin_unloaded"
    
    # Command lifecycle events
    COMMAND_START = "command_start"
    COMMAND_END = "command_end"
    COMMAND_ERROR = "command_error"
    
    # Application lifecycle events
    APP_STARTING = "app_starting"
    APP_STARTED = "app_started"
    APP_STOPPING = "app_stopping"
    APP_STOPPED = "app_stopped"
    
    # Configuration events
    CONFIG_LOADED = "config_loaded"
    CONFIG_CHANGED = "config_changed"
    
    # Custom events (plugins can define their own)
    CUSTOM = "custom"


@dataclass
class Event:
    """
    Event data structure.
    
    Contains all information about an event including type, source,
    data payload, and metadata.
    """
    
    event_type: Union[EventType, str]
    source: str
    data: Dict[str, Any]
    timestamp: datetime
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())


EventHandler = Callable[[Event], Union[None, asyncio.Future]]


class EventBus:
    """
    Asyncio-based event bus for publish-subscribe messaging.
    
    Supports both sync and async event handlers, weak references to prevent
    memory leaks, and event filtering based on type and source.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Set[EventHandler]] = {}
        self._weak_handlers: Dict[str, Set] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'handlers_called': 0,
            'errors': 0
        }
    
    async def start(self) -> None:
        """Start the event bus processor."""
        if self._running:
            logger.warning("Event bus is already running")
            return
            
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event bus processor."""
        if not self._running:
            return
            
        self._running = False
        
        # Signal processor to stop
        await self._event_queue.put(None)
        
        if self._processor_task:
            try:
                await asyncio.wait_for(self._processor_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Event bus processor did not stop gracefully")
                self._processor_task.cancel()
        
        logger.info("Event bus stopped")
    
    def subscribe(self, event_type: Union[EventType, str], handler: EventHandler, weak: bool = True) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of events to subscribe to
            handler: Function to call when event occurs
            weak: Whether to use weak references (prevents memory leaks)
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type
        
        if weak:
            # Use weak references to prevent memory leaks
            if event_key not in self._weak_handlers:
                self._weak_handlers[event_key] = set()
            
            weak_ref = weakref.ref(handler, lambda ref: self._cleanup_weak_ref(event_key, ref))
            self._weak_handlers[event_key].add(weak_ref)
        else:
            # Use strong references
            if event_key not in self._handlers:
                self._handlers[event_key] = set()
            
            self._handlers[event_key].add(handler)
        
        logger.debug(f"Subscribed to {event_key} with {'weak' if weak else 'strong'} reference")
    
    def unsubscribe(self, event_type: Union[EventType, str], handler: EventHandler) -> None:
        """
        Unsubscribe from events of a specific type.
        
        Args:
            event_type: Type of events to unsubscribe from
            handler: Handler function to remove
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type
        
        # Remove from strong references
        if event_key in self._handlers:
            self._handlers[event_key].discard(handler)
            if not self._handlers[event_key]:
                del self._handlers[event_key]
        
        # Remove from weak references
        if event_key in self._weak_handlers:
            to_remove = []
            for weak_ref in self._weak_handlers[event_key]:
                if weak_ref() is handler:
                    to_remove.append(weak_ref)
            
            for weak_ref in to_remove:
                self._weak_handlers[event_key].discard(weak_ref)
            
            if not self._weak_handlers[event_key]:
                del self._weak_handlers[event_key]
        
        logger.debug(f"Unsubscribed from {event_key}")
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event: Event to publish
        """
        if not self._running:
            logger.warning("Event bus is not running, event will be queued")
        
        await self._event_queue.put(event)
        self._stats['events_published'] += 1
        
        logger.debug(f"Published event {event.event_type} from {event.source}")
    
    async def publish_event(
        self,
        event_type: Union[EventType, str],
        source: str,
        data: Dict[str, Any] = None,
        **kwargs
    ) -> None:
        """
        Convenience method to publish an event.
        
        Args:
            event_type: Type of event
            source: Source of the event
            data: Event data payload
            **kwargs: Additional event metadata
        """
        event = Event(
            event_type=event_type,
            source=source,
            data=data or {},
            timestamp=datetime.now(),
            **kwargs
        )
        await self.publish(event)
    
    async def _process_events(self) -> None:
        """Process events from the queue."""
        logger.debug("Event processor started")
        
        while self._running:
            try:
                # Wait for next event
                event = await self._event_queue.get()
                
                # None is the stop signal
                if event is None:
                    break
                
                await self._handle_event(event)
                self._stats['events_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                self._stats['errors'] += 1
        
        logger.debug("Event processor stopped")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle a single event by calling all registered handlers."""
        event_key = event.event_type.value if isinstance(event.event_type, EventType) else event.event_type
        
        handlers = []
        
        # Collect strong reference handlers
        if event_key in self._handlers:
            handlers.extend(self._handlers[event_key])
        
        # Collect weak reference handlers
        if event_key in self._weak_handlers:
            for weak_ref in list(self._weak_handlers[event_key]):  # Copy to avoid modification during iteration
                handler = weak_ref()
                if handler is not None:
                    handlers.append(handler)
                else:
                    # Clean up dead weak reference
                    self._weak_handlers[event_key].discard(weak_ref)
        
        # Call all handlers
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
                
                self._stats['handlers_called'] += 1
                
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__}: {e}")
                self._stats['errors'] += 1
    
    def _cleanup_weak_ref(self, event_key: str, weak_ref) -> None:
        """Clean up a dead weak reference."""
        if event_key in self._weak_handlers:
            self._weak_handlers[event_key].discard(weak_ref)
            if not self._weak_handlers[event_key]:
                del self._weak_handlers[event_key]
    
    def get_stats(self) -> Dict[str, int]:
        """Get event bus statistics."""
        return self._stats.copy()
    
    def get_handler_count(self, event_type: Union[EventType, str] = None) -> int:
        """Get the number of handlers for a specific event type or all events."""
        if event_type is None:
            # Count all handlers
            total = sum(len(handlers) for handlers in self._handlers.values())
            total += sum(len(handlers) for handlers in self._weak_handlers.values())
            return total
        
        event_key = event_type.value if isinstance(event_type, EventType) else event_type
        count = 0
        
        if event_key in self._handlers:
            count += len(self._handlers[event_key])
        
        if event_key in self._weak_handlers:
            count += len(self._weak_handlers[event_key])
        
        return count


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def start_event_bus() -> None:
    """Start the global event bus."""
    bus = get_event_bus()
    await bus.start()


async def stop_event_bus() -> None:
    """Stop the global event bus."""
    global _event_bus
    if _event_bus is not None:
        await _event_bus.stop()
        _event_bus = None

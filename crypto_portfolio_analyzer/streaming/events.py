"""Event-driven system for broadcasting real-time updates."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json
import weakref
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of streaming events."""
    PRICE_UPDATE = "price_update"
    PORTFOLIO_UPDATE = "portfolio_update"
    ALERT_TRIGGERED = "alert_triggered"
    CONNECTION_STATUS = "connection_status"
    MARKET_DATA = "market_data"
    SYSTEM_STATUS = "system_status"
    USER_ACTION = "user_action"


@dataclass
class StreamEvent:
    """Base event for the streaming system."""
    
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    async def handle_event(self, event: StreamEvent) -> bool:
        """Handle an event. Return True if event was processed successfully."""
        pass
    
    @abstractmethod
    def get_supported_event_types(self) -> Set[EventType]:
        """Return set of event types this handler supports."""
        pass


class EventFilter:
    """Filter for events based on various criteria."""
    
    def __init__(self, 
                 event_types: Optional[Set[EventType]] = None,
                 sources: Optional[Set[str]] = None,
                 symbols: Optional[Set[str]] = None,
                 custom_filter: Optional[Callable[[StreamEvent], bool]] = None):
        self.event_types = event_types or set()
        self.sources = sources or set()
        self.symbols = symbols or set()
        self.custom_filter = custom_filter
    
    def matches(self, event: StreamEvent) -> bool:
        """Check if event matches this filter."""
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Check source
        if self.sources and event.source not in self.sources:
            return False
        
        # Check symbol (if present in event data)
        if self.symbols:
            event_symbol = event.data.get("symbol")
            if event_symbol and event_symbol not in self.symbols:
                return False
        
        # Check custom filter
        if self.custom_filter and not self.custom_filter(event):
            return False
        
        return True


class EventSubscription:
    """Represents a subscription to events."""
    
    def __init__(self, 
                 subscription_id: str,
                 handler: Union[EventHandler, Callable[[StreamEvent], None]],
                 event_filter: Optional[EventFilter] = None,
                 priority: int = 0):
        self.subscription_id = subscription_id
        self.handler = handler
        self.event_filter = event_filter or EventFilter()
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.event_count = 0
        self.last_event_time: Optional[datetime] = None
        self.error_count = 0
        
    async def handle_event(self, event: StreamEvent) -> bool:
        """Handle an event if it matches the filter."""
        if not self.event_filter.matches(event):
            return False
        
        try:
            self.event_count += 1
            self.last_event_time = datetime.now(timezone.utc)
            
            if isinstance(self.handler, EventHandler):
                return await self.handler.handle_event(event)
            elif asyncio.iscoroutinefunction(self.handler):
                await self.handler(event)
                return True
            else:
                self.handler(event)
                return True
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error in event handler {self.subscription_id}: {e}")
            return False


class StreamEventBus:
    """Central event bus for streaming system."""
    
    def __init__(self, max_queue_size: int = 10000):
        self.subscriptions: Dict[str, EventSubscription] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.event_history: List[StreamEvent] = []
        self.max_history_size = 1000
        
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "active_subscriptions": 0
        }
    
    async def start(self):
        """Start the event bus."""
        if self._running:
            return
            
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self):
        """Stop the event bus."""
        if not self._running:
            return
            
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            
        # Clear queue
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
                
        logger.info("Event bus stopped")
    
    def subscribe(self, 
                  subscription_id: str,
                  handler: Union[EventHandler, Callable[[StreamEvent], None]],
                  event_filter: Optional[EventFilter] = None,
                  priority: int = 0) -> bool:
        """Subscribe to events."""
        if subscription_id in self.subscriptions:
            logger.warning(f"Subscription {subscription_id} already exists")
            return False
        
        subscription = EventSubscription(
            subscription_id=subscription_id,
            handler=handler,
            event_filter=event_filter,
            priority=priority
        )
        
        self.subscriptions[subscription_id] = subscription
        self._stats["active_subscriptions"] = len(self.subscriptions)
        
        logger.info(f"Added subscription: {subscription_id}")
        return True
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id not in self.subscriptions:
            logger.warning(f"Subscription {subscription_id} not found")
            return False
        
        del self.subscriptions[subscription_id]
        self._stats["active_subscriptions"] = len(self.subscriptions)
        
        logger.info(f"Removed subscription: {subscription_id}")
        return True
    
    async def publish(self, event: StreamEvent) -> bool:
        """Publish an event to the bus."""
        if not self._running:
            logger.warning("Event bus not running - dropping event")
            return False
        
        try:
            self.event_queue.put_nowait(event)
            self._stats["events_published"] += 1
            return True
            
        except asyncio.QueueFull:
            self._stats["events_dropped"] += 1
            logger.warning("Event queue full - dropping event")
            return False
    
    async def publish_price_update(self, symbol: str, price_data: Dict[str, Any], source: str = "price_feed"):
        """Convenience method to publish price update event."""
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": symbol, **price_data},
            source=source
        )
        await self.publish(event)
    
    async def publish_portfolio_update(self, portfolio_data: Dict[str, Any], source: str = "portfolio_monitor"):
        """Convenience method to publish portfolio update event."""
        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data=portfolio_data,
            source=source
        )
        await self.publish(event)
    
    async def publish_alert(self, alert_data: Dict[str, Any], source: str = "alert_system"):
        """Convenience method to publish alert event."""
        event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data=alert_data,
            source=source
        )
        await self.publish(event)
    
    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                # Get event from queue with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Add to history
                self.event_history.append(event)
                if len(self.event_history) > self.max_history_size:
                    self.event_history.pop(0)
                
                # Process event with all matching subscriptions
                await self._dispatch_event(event)
                self._stats["events_processed"] += 1
                
            except asyncio.TimeoutError:
                continue  # No events to process
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _dispatch_event(self, event: StreamEvent):
        """Dispatch event to all matching subscriptions."""
        # Sort subscriptions by priority (higher priority first)
        sorted_subscriptions = sorted(
            self.subscriptions.values(),
            key=lambda s: s.priority,
            reverse=True
        )
        
        # Dispatch to all matching subscriptions concurrently
        tasks = []
        for subscription in sorted_subscriptions:
            if subscription.event_filter.matches(event):
                task = asyncio.create_task(subscription.handle_event(event))
                tasks.append(task)
        
        if tasks:
            # Wait for all handlers to complete
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_subscription_stats(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific subscription."""
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        return {
            "subscription_id": subscription.subscription_id,
            "created_at": subscription.created_at.isoformat(),
            "event_count": subscription.event_count,
            "last_event_time": subscription.last_event_time.isoformat() if subscription.last_event_time else None,
            "error_count": subscription.error_count,
            "priority": subscription.priority
        }
    
    def get_bus_stats(self) -> Dict[str, Any]:
        """Get overall event bus statistics."""
        return {
            **self._stats,
            "queue_size": self.event_queue.qsize(),
            "history_size": len(self.event_history),
            "running": self._running
        }
    
    def get_recent_events(self, limit: int = 100, event_type: Optional[EventType] = None) -> List[Dict[str, Any]]:
        """Get recent events from history."""
        events = self.event_history[-limit:] if limit > 0 else self.event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return [event.to_dict() for event in events]


class WebSocketEventHandler(EventHandler):
    """Event handler that broadcasts events to WebSocket clients."""
    
    def __init__(self, websocket_server):
        self.websocket_server = weakref.ref(websocket_server)
        self.supported_events = {
            EventType.PRICE_UPDATE,
            EventType.PORTFOLIO_UPDATE,
            EventType.ALERT_TRIGGERED,
            EventType.SYSTEM_STATUS
        }
    
    async def handle_event(self, event: StreamEvent) -> bool:
        """Handle event by broadcasting to WebSocket clients."""
        server = self.websocket_server()
        if not server:
            return False
        
        try:
            if event.event_type == EventType.PRICE_UPDATE:
                symbol = event.data.get("symbol")
                if symbol:
                    await server.broadcast_price_update(symbol, event.data)
            
            elif event.event_type == EventType.PORTFOLIO_UPDATE:
                await server.broadcast_portfolio_update(event.data)
            
            elif event.event_type == EventType.ALERT_TRIGGERED:
                await server.send_alert(event.data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error broadcasting event to WebSocket clients: {e}")
            return False
    
    def get_supported_event_types(self) -> Set[EventType]:
        """Return supported event types."""
        return self.supported_events


class DatabaseEventHandler(EventHandler):
    """Event handler that persists events to database."""
    
    def __init__(self, database_manager):
        self.database_manager = weakref.ref(database_manager)
        self.supported_events = {
            EventType.PRICE_UPDATE,
            EventType.PORTFOLIO_UPDATE,
            EventType.ALERT_TRIGGERED
        }
    
    async def handle_event(self, event: StreamEvent) -> bool:
        """Handle event by persisting to database."""
        db = self.database_manager()
        if not db:
            return False
        
        try:
            # This would integrate with your database layer
            # For now, just log the event
            logger.info(f"Persisting event to database: {event.event_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error persisting event to database: {e}")
            return False
    
    def get_supported_event_types(self) -> Set[EventType]:
        """Return supported event types."""
        return self.supported_events

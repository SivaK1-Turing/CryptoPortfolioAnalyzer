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
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamEvent':
        """Create event from dictionary."""
        return cls(
            event_type=EventType(data['event_type']),
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')),
            source=data.get('source'),
            event_id=data.get('event_id'),
            correlation_id=data.get('correlation_id')
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'StreamEvent':
        """Create event from JSON string."""
        return cls.from_dict(json.loads(json_str))


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


class WebSocketEventBroadcaster:
    """WebSocket-based event broadcaster for real-time updates."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize WebSocket broadcaster.

        Args:
            host: WebSocket server host
            port: WebSocket server port
        """
        self.host = host
        self.port = port
        self.server = None
        self.clients: Set[Any] = set()  # WebSocket connections
        self.running = False

    async def start(self):
        """Start WebSocket server."""
        try:
            import websockets

            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port
            )
            self.running = True
            logger.info(f"WebSocket event broadcaster started on {self.host}:{self.port}")

        except ImportError:
            logger.error("websockets library not installed. Install with: pip install websockets")
            raise
        except Exception as e:
            logger.error(f"Failed to start WebSocket broadcaster: {e}")
            raise

    async def stop(self):
        """Stop WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.running = False
            logger.info("WebSocket event broadcaster stopped")

    async def broadcast_event(self, event: StreamEvent):
        """Broadcast event to all connected clients."""
        if not self.clients:
            return

        message = event.to_json()
        disconnected_clients = set()

        for client in self.clients:
            try:
                await client.send(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected_clients.add(client)

        # Remove disconnected clients
        self.clients -= disconnected_clients

        if disconnected_clients:
            logger.info(f"Removed {len(disconnected_clients)} disconnected clients")

    async def _handle_client(self, websocket, path):
        """Handle new WebSocket client connection."""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"New WebSocket client connected: {client_addr}")

        try:
            # Send welcome message
            welcome_event = StreamEvent(
                event_type=EventType.CONNECTION_STATUS,
                data={"status": "connected", "message": "Welcome to real-time portfolio updates"},
                source="websocket_broadcaster"
            )
            await websocket.send(welcome_event.to_json())

            # Keep connection alive
            async for message in websocket:
                # Handle client messages (ping/pong, subscriptions, etc.)
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        pong_event = StreamEvent(
                            event_type=EventType.CONNECTION_STATUS,
                            data={"type": "pong"},
                            source="websocket_broadcaster"
                        )
                        await websocket.send(pong_event.to_json())
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client_addr}: {message}")

        except Exception as e:
            logger.info(f"Client {client_addr} disconnected: {e}")
        finally:
            self.clients.discard(websocket)

    def get_client_count(self) -> int:
        """Get number of connected clients."""
        return len(self.clients)


class MessageQueue:
    """Simple in-memory message queue for event distribution."""

    def __init__(self, max_size: int = 10000):
        """Initialize message queue.

        Args:
            max_size: Maximum queue size
        """
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.consumers: Set[Callable[[StreamEvent], None]] = set()
        self.running = False
        self._consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start message queue consumer."""
        if self.running:
            return

        self.running = True
        self._consumer_task = asyncio.create_task(self._consume_messages())
        logger.info("Message queue started")

    async def stop(self):
        """Stop message queue consumer."""
        if not self.running:
            return

        self.running = False

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        logger.info("Message queue stopped")

    async def publish(self, event: StreamEvent):
        """Publish event to queue."""
        try:
            await self.queue.put(event)
        except asyncio.QueueFull:
            logger.warning("Message queue is full, dropping event")

    def add_consumer(self, consumer: Callable[[StreamEvent], None]):
        """Add event consumer."""
        self.consumers.add(consumer)

    def remove_consumer(self, consumer: Callable[[StreamEvent], None]):
        """Remove event consumer."""
        self.consumers.discard(consumer)

    async def _consume_messages(self):
        """Consume messages from queue."""
        while self.running:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                # Distribute to all consumers
                for consumer in self.consumers:
                    try:
                        if asyncio.iscoroutinefunction(consumer):
                            asyncio.create_task(consumer(event))
                        else:
                            consumer(event)
                    except Exception as e:
                        logger.error(f"Error in message queue consumer: {e}")

                self.queue.task_done()

            except asyncio.TimeoutError:
                continue  # Check if still running
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error consuming message: {e}")

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()


class EnhancedStreamEventBus(StreamEventBus):
    """Enhanced event bus with WebSocket broadcasting and message queues."""

    def __init__(self):
        """Initialize enhanced event bus."""
        super().__init__()
        self.websocket_broadcaster: Optional[WebSocketEventBroadcaster] = None
        self.message_queue: Optional[MessageQueue] = None
        self.enable_websocket = False
        self.enable_message_queue = False

    async def start_websocket_broadcaster(self, host: str = "localhost", port: int = 8765):
        """Start WebSocket broadcaster.

        Args:
            host: WebSocket server host
            port: WebSocket server port
        """
        self.websocket_broadcaster = WebSocketEventBroadcaster(host, port)
        await self.websocket_broadcaster.start()
        self.enable_websocket = True

        # Subscribe to all events for broadcasting
        self.subscribe(
            "websocket_broadcaster",
            self._broadcast_to_websocket,
            event_types=set(EventType)
        )

    async def start_message_queue(self, max_size: int = 10000):
        """Start message queue.

        Args:
            max_size: Maximum queue size
        """
        self.message_queue = MessageQueue(max_size)
        await self.message_queue.start()
        self.enable_message_queue = True

        # Subscribe to all events for queuing
        self.subscribe(
            "message_queue",
            self._publish_to_queue,
            event_types=set(EventType)
        )

    async def stop(self):
        """Stop enhanced event bus."""
        if self.websocket_broadcaster:
            await self.websocket_broadcaster.stop()

        if self.message_queue:
            await self.message_queue.stop()

        await super().stop()

    async def _broadcast_to_websocket(self, event: StreamEvent):
        """Broadcast event to WebSocket clients."""
        if self.websocket_broadcaster and self.enable_websocket:
            await self.websocket_broadcaster.broadcast_event(event)

    async def _publish_to_queue(self, event: StreamEvent):
        """Publish event to message queue."""
        if self.message_queue and self.enable_message_queue:
            await self.message_queue.publish(event)

    def get_websocket_client_count(self) -> int:
        """Get number of WebSocket clients."""
        if self.websocket_broadcaster:
            return self.websocket_broadcaster.get_client_count()
        return 0

    def get_message_queue_size(self) -> int:
        """Get message queue size."""
        if self.message_queue:
            return self.message_queue.get_queue_size()
        return 0

    def add_queue_consumer(self, consumer: Callable[[StreamEvent], None]):
        """Add message queue consumer."""
        if self.message_queue:
            self.message_queue.add_consumer(consumer)

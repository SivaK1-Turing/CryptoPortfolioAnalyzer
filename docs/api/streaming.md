# Streaming API Reference

This document provides detailed API reference for the streaming components of the Crypto Portfolio Analyzer.

## Core Classes

### StreamManager

Manages WebSocket connections and message routing.

```python
class StreamManager:
    def __init__(self, max_connections: int = 100)
```

#### Methods

##### `async start() -> None`
Start the stream manager and begin monitoring connections.

##### `async stop() -> None`
Stop the stream manager and close all connections.

##### `async add_stream(config: StreamConfig) -> bool`
Add a new stream connection.

**Parameters:**
- `config`: StreamConfig object with connection details

**Returns:**
- `bool`: True if stream was added successfully

##### `async remove_stream(stream_id: str) -> None`
Remove and close a stream connection.

**Parameters:**
- `stream_id`: Unique identifier for the stream

##### `get_stream_status(stream_id: str) -> Optional[StreamStatus]`
Get the current status of a stream.

**Parameters:**
- `stream_id`: Unique identifier for the stream

**Returns:**
- `StreamStatus`: Current stream status or None if not found

##### `get_stream_metrics(stream_id: str) -> Optional[StreamMetrics]`
Get performance metrics for a stream.

**Parameters:**
- `stream_id`: Unique identifier for the stream

**Returns:**
- `StreamMetrics`: Performance metrics or None if not found

##### `add_global_handler(handler: Callable) -> None`
Add a global message handler for all streams.

**Parameters:**
- `handler`: Function to handle messages

### StreamConfig

Configuration for WebSocket stream connections.

```python
@dataclass
class StreamConfig:
    stream_id: str
    url: str
    symbols: List[str] = field(default_factory=list)
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    max_reconnect_delay: float = 60.0
    heartbeat_interval: float = 30.0
    buffer_size: int = 1000
    rate_limit: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
```

### StreamConnection

Represents a single WebSocket connection.

```python
class StreamConnection:
    def __init__(self, config: StreamConfig, manager: StreamManager)
```

#### Methods

##### `async connect() -> bool`
Establish the WebSocket connection.

**Returns:**
- `bool`: True if connection was successful

##### `async disconnect() -> None`
Close the WebSocket connection.

##### `async send_message(message: Dict[str, Any]) -> None`
Send a message through the WebSocket.

**Parameters:**
- `message`: Dictionary containing the message data

##### `add_handler(handler: Callable) -> None`
Add a message handler for this connection.

**Parameters:**
- `handler`: Function to handle incoming messages

##### `remove_handler(handler: Callable) -> None`
Remove a message handler.

**Parameters:**
- `handler`: Function to remove

### StreamStatus

Enumeration of possible stream states.

```python
class StreamStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
```

### StreamMetrics

Performance metrics for stream connections.

```python
@dataclass
class StreamMetrics:
    messages_received: int = 0
    messages_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    connection_count: int = 0
    reconnection_count: int = 0
    error_count: int = 0
    last_message_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    latency_ms: float = 0.0
```

## Price Feed Classes

### PriceFeedManager

Manages multiple price feed providers and aggregates data.

```python
class PriceFeedManager:
    def __init__(self)
```

#### Methods

##### `add_provider(provider: PriceFeedProvider, symbols: List[str], is_primary: bool = False) -> None`
Add a price feed provider.

**Parameters:**
- `provider`: Provider type (BINANCE, COINBASE, MOCK)
- `symbols`: List of symbols to track
- `is_primary`: Whether this is the primary provider

##### `async start() -> None`
Start all configured price feeds.

##### `async stop() -> None`
Stop all price feeds.

##### `add_handler(handler: Callable[[PriceUpdate], None]) -> None`
Add a price update handler.

**Parameters:**
- `handler`: Function to handle price updates

##### `get_last_update_time(symbol: str) -> Optional[datetime]`
Get the timestamp of the last price update for a symbol.

**Parameters:**
- `symbol`: Symbol to check

**Returns:**
- `datetime`: Last update time or None

##### `get_provider_status() -> Dict[str, Dict[str, Any]]`
Get status information for all providers.

**Returns:**
- `dict`: Provider status information

### PriceUpdate

Data structure for price updates.

```python
@dataclass
class PriceUpdate:
    symbol: str
    price: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    volume_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[float] = None
    source: DataSource = DataSource.MANUAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
```

### BasePriceFeed

Base class for price feed implementations.

```python
class BasePriceFeed:
    def __init__(self, provider: PriceFeedProvider, symbols: List[str])
```

#### Methods

##### `async start() -> None`
Start the price feed.

##### `async stop() -> None`
Stop the price feed.

##### `add_handler(handler: Callable[[PriceUpdate], None]) -> None`
Add a price update handler.

##### `add_symbol(symbol: str) -> None`
Add a symbol to track.

##### `remove_symbol(symbol: str) -> None`
Remove a symbol from tracking.

### MockPriceFeed

Mock price feed for testing and development.

```python
class MockPriceFeed(BasePriceFeed):
    def __init__(self, symbols: List[str], update_interval: float = 1.0)
```

## Event System Classes

### StreamEventBus

Central event bus for publish/subscribe messaging.

```python
class StreamEventBus:
    def __init__(self, max_queue_size: int = 10000, max_history_size: int = 1000)
```

#### Methods

##### `async start() -> None`
Start the event bus.

##### `async stop() -> None`
Stop the event bus and clear all subscriptions.

##### `subscribe(subscription_id: str, handler: Union[Callable, EventHandler], event_filter: Optional[EventFilter] = None, priority: int = 0) -> bool`
Subscribe to events.

**Parameters:**
- `subscription_id`: Unique identifier for the subscription
- `handler`: Function or EventHandler to process events
- `event_filter`: Optional filter for events
- `priority`: Priority level (higher = processed first)

**Returns:**
- `bool`: True if subscription was successful

##### `unsubscribe(subscription_id: str) -> bool`
Remove a subscription.

**Parameters:**
- `subscription_id`: Subscription to remove

**Returns:**
- `bool`: True if subscription was removed

##### `async publish(event: StreamEvent) -> bool`
Publish an event to the bus.

**Parameters:**
- `event`: Event to publish

**Returns:**
- `bool`: True if event was published successfully

##### `async publish_price_update(symbol: str, data: Dict[str, Any]) -> bool`
Convenience method to publish price update events.

**Parameters:**
- `symbol`: Symbol for the price update
- `data`: Price data

##### `async publish_portfolio_update(data: Dict[str, Any]) -> bool`
Convenience method to publish portfolio update events.

**Parameters:**
- `data`: Portfolio data

##### `async publish_alert(data: Dict[str, Any]) -> bool`
Convenience method to publish alert events.

**Parameters:**
- `data`: Alert data

##### `get_bus_stats() -> Dict[str, Any]`
Get event bus statistics.

**Returns:**
- `dict`: Statistics including events published, processed, etc.

##### `get_recent_events(limit: int = 100, event_type: Optional[EventType] = None) -> List[Dict[str, Any]]`
Get recent events from history.

**Parameters:**
- `limit`: Maximum number of events to return
- `event_type`: Optional filter by event type

**Returns:**
- `list`: Recent events as dictionaries

### StreamEvent

Event data structure.

```python
@dataclass
class StreamEvent:
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
    
    def to_json(self) -> str:
        """Convert to JSON string."""
```

### EventType

Enumeration of event types.

```python
class EventType(Enum):
    PRICE_UPDATE = "price_update"
    PORTFOLIO_UPDATE = "portfolio_update"
    ALERT_TRIGGERED = "alert_triggered"
    SYSTEM_STATUS = "system_status"
    CONNECTION_STATUS = "connection_status"
    ERROR = "error"
```

### EventFilter

Filter for event subscriptions.

```python
@dataclass
class EventFilter:
    event_types: Optional[Set[EventType]] = None
    sources: Optional[Set[str]] = None
    symbols: Optional[Set[str]] = None
    custom_filter: Optional[Callable[[StreamEvent], bool]] = None
    
    def matches(self, event: StreamEvent) -> bool:
        """Check if event matches this filter."""
```

### EventHandler

Abstract base class for event handlers.

```python
class EventHandler(ABC):
    @abstractmethod
    async def handle_event(self, event: StreamEvent) -> bool:
        """Handle an event. Return True if handled successfully."""
    
    def get_supported_event_types(self) -> Set[EventType]:
        """Return set of supported event types."""
```

## WebSocket Server Classes

### WebSocketServer

FastAPI-based WebSocket server for real-time communication.

```python
class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 8000)
```

#### Methods

##### `async start() -> None`
Start the WebSocket server.

##### `async stop() -> None`
Stop the WebSocket server.

##### `async broadcast_price_update(symbol: str, data: Dict[str, Any]) -> None`
Broadcast price update to all connected clients.

**Parameters:**
- `symbol`: Symbol for the price update
- `data`: Price data

##### `async broadcast_portfolio_update(data: Dict[str, Any]) -> None`
Broadcast portfolio update to all connected clients.

**Parameters:**
- `data`: Portfolio data

##### `async send_alert(data: Dict[str, Any], room: Optional[str] = None) -> None`
Send alert to clients.

**Parameters:**
- `data`: Alert data
- `room`: Optional room to send to (default: all clients)

### ConnectionManager

Manages WebSocket client connections.

```python
class ConnectionManager:
    def __init__(self)
```

#### Methods

##### `async start() -> None`
Start the connection manager.

##### `async stop() -> None`
Stop the connection manager and disconnect all clients.

##### `async connect_client(websocket: WebSocket, client_id: Optional[str] = None) -> str`
Connect a new client.

**Parameters:**
- `websocket`: WebSocket connection
- `client_id`: Optional custom client ID

**Returns:**
- `str`: Assigned client ID

##### `async disconnect_client(client_id: str) -> None`
Disconnect a client.

**Parameters:**
- `client_id`: Client to disconnect

##### `async join_room(client_id: str, room: str) -> None`
Add client to a room.

**Parameters:**
- `client_id`: Client ID
- `room`: Room name

##### `async leave_room(client_id: str, room: str) -> None`
Remove client from a room.

**Parameters:**
- `client_id`: Client ID
- `room`: Room name

##### `async send_to_client(client_id: str, message: WebSocketMessage) -> None`
Send message to specific client.

**Parameters:**
- `client_id`: Target client
- `message`: Message to send

##### `async broadcast_to_room(room: str, message: WebSocketMessage) -> None`
Broadcast message to all clients in a room.

**Parameters:**
- `room`: Target room
- `message`: Message to broadcast

##### `async broadcast_to_all(message: WebSocketMessage) -> None`
Broadcast message to all connected clients.

**Parameters:**
- `message`: Message to broadcast

##### `get_client_count() -> int`
Get total number of connected clients.

##### `get_room_client_count(room: str) -> int`
Get number of clients in a specific room.

##### `get_client_info(client_id: str) -> Optional[Dict[str, Any]]`
Get information about a specific client.

**Parameters:**
- `client_id`: Client to get info for

**Returns:**
- `dict`: Client information or None if not found

### WebSocketMessage

Message structure for WebSocket communication.

```python
@dataclass
class WebSocketMessage:
    type: MessageType
    data: Dict[str, Any]
    client_id: Optional[str] = None
    room: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
```

### MessageType

Enumeration of WebSocket message types.

```python
class MessageType(Enum):
    PRICE_UPDATE = "price_update"
    PORTFOLIO_UPDATE = "portfolio_update"
    ALERT = "alert"
    STATUS = "status"
    ERROR = "error"
    SYSTEM_STATUS = "system_status"
```

## Portfolio Monitoring Classes

### PortfolioMonitor

Real-time portfolio value monitoring.

```python
class PortfolioMonitor:
    def __init__(self)
```

#### Methods

##### `add_holding(symbol: str, amount: Decimal) -> None`
Add a holding to monitor.

**Parameters:**
- `symbol`: Symbol to track
- `amount`: Amount held

##### `remove_holding(symbol: str) -> None`
Remove a holding from monitoring.

**Parameters:**
- `symbol`: Symbol to remove

##### `update_holding(symbol: str, amount: Decimal) -> None`
Update the amount of a holding.

**Parameters:**
- `symbol`: Symbol to update
- `amount`: New amount

##### `async start_monitoring(provider: PriceFeedProvider = PriceFeedProvider.MOCK) -> None`
Start monitoring portfolio values.

**Parameters:**
- `provider`: Price feed provider to use

##### `async stop_monitoring() -> None`
Stop monitoring portfolio values.

##### `get_current_value() -> Decimal`
Get current total portfolio value.

**Returns:**
- `Decimal`: Current portfolio value

##### `get_holdings_summary() -> Dict[str, Dict[str, Any]]`
Get summary of all holdings.

**Returns:**
- `dict`: Holdings with current values and changes

##### `add_value_change_handler(handler: Callable[[Dict[str, Any]], None]) -> None`
Add handler for portfolio value changes.

**Parameters:**
- `handler`: Function to handle value changes

## Exceptions

### StreamingError

Base exception for streaming-related errors.

```python
class StreamingError(Exception):
    """Base exception for streaming operations."""
```

### ConnectionError

Exception for connection-related errors.

```python
class ConnectionError(StreamingError):
    """Exception for connection failures."""
```

### DataError

Exception for data-related errors.

```python
class DataError(StreamingError):
    """Exception for data processing errors."""
```

### ConfigurationError

Exception for configuration-related errors.

```python
class ConfigurationError(StreamingError):
    """Exception for configuration errors."""
```

## Type Hints

Common type hints used throughout the streaming API:

```python
from typing import Dict, List, Optional, Callable, Any, Union, Set
from decimal import Decimal
from datetime import datetime

# Handler function types
MessageHandler = Callable[[Dict[str, Any]], None]
PriceHandler = Callable[[PriceUpdate], None]
EventHandler = Union[Callable[[StreamEvent], None], Callable[[StreamEvent], Awaitable[None]]]

# Data types
PriceData = Dict[str, Union[str, float, Decimal, datetime]]
PortfolioData = Dict[str, Union[str, float, Decimal, List[Dict[str, Any]]]]
MetricsData = Dict[str, Union[int, float, str, datetime]]
```

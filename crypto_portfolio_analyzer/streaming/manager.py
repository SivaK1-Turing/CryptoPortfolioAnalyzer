"""Real-time data stream manager for handling multiple concurrent data streams."""

import asyncio
import logging
import time
import websockets
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import weakref
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    """Stream connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StreamConfig:
    """Configuration for a data stream."""
    
    stream_id: str
    url: str
    symbols: List[str] = field(default_factory=list)
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    max_reconnect_delay: float = 60.0
    heartbeat_interval: float = 30.0
    buffer_size: int = 1000
    rate_limit: Optional[float] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamMetrics:
    """Metrics for stream performance monitoring."""
    
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


class StreamConnection:
    """Represents a single stream connection with automatic reconnection."""
    
    def __init__(self, config: StreamConfig, manager: 'StreamManager'):
        self.config = config
        self.manager = weakref.ref(manager)
        self.status = StreamStatus.DISCONNECTED
        self.websocket: Optional[Any] = None
        self.metrics = StreamMetrics()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=config.buffer_size)
        self._handlers: Set[Callable] = set()
        self._last_heartbeat = time.time()
        self._connection_start_time: Optional[float] = None
        
    async def connect(self) -> bool:
        """Establish connection to the stream."""
        if self.status in [StreamStatus.CONNECTED, StreamStatus.CONNECTING]:
            return True
            
        self.status = StreamStatus.CONNECTING
        logger.info(f"Connecting to stream {self.config.stream_id}")
        
        try:
            import websockets
            
            # Create WebSocket connection
            self.websocket = await websockets.connect(
                self.config.url,
                extra_headers=self.config.headers,
                ping_interval=self.config.heartbeat_interval,
                ping_timeout=10
            )
            
            self.status = StreamStatus.CONNECTED
            self.metrics.connection_count += 1
            self._connection_start_time = time.time()
            
            # Start message processing and heartbeat
            asyncio.create_task(self._process_messages())
            if self.config.heartbeat_interval > 0:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info(f"Connected to stream {self.config.stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to stream {self.config.stream_id}: {e}")
            self.status = StreamStatus.ERROR
            self.metrics.error_count += 1
            return False
    
    async def disconnect(self):
        """Disconnect from the stream."""
        logger.info(f"Disconnecting from stream {self.config.stream_id}")
        
        self.status = StreamStatus.DISCONNECTED
        
        # Cancel tasks
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        # Update metrics
        if self._connection_start_time:
            self.metrics.uptime_seconds += time.time() - self._connection_start_time
            self._connection_start_time = None
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message to the stream."""
        if not self.websocket or self.status != StreamStatus.CONNECTED:
            logger.warning(f"Cannot send message - stream {self.config.stream_id} not connected")
            return
            
        try:
            import json
            message_str = json.dumps(message)
            await self.websocket.send(message_str)
            self.metrics.messages_sent += 1
            self.metrics.bytes_sent += len(message_str.encode())
            
        except Exception as e:
            logger.error(f"Failed to send message to stream {self.config.stream_id}: {e}")
            self.metrics.error_count += 1
    
    def add_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Add message handler."""
        self._handlers.add(handler)
    
    def remove_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Remove message handler."""
        self._handlers.discard(handler)
    
    async def _process_messages(self):
        """Process incoming messages from the stream."""
        try:
            async for message in self.websocket:
                try:
                    import json
                    data = json.loads(message)
                    
                    # Update metrics
                    self.metrics.messages_received += 1
                    self.metrics.bytes_received += len(message.encode())
                    self.metrics.last_message_time = datetime.now(timezone.utc)
                    
                    # Add to queue
                    try:
                        self._message_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        logger.warning(f"Message queue full for stream {self.config.stream_id}")
                        # Remove oldest message
                        try:
                            self._message_queue.get_nowait()
                            self._message_queue.put_nowait(data)
                        except asyncio.QueueEmpty:
                            pass
                    
                    # Call handlers
                    for handler in self._handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                asyncio.create_task(handler(data))
                            else:
                                handler(data)
                        except Exception as e:
                            logger.error(f"Error in message handler: {e}")
                            
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received from stream {self.config.stream_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing messages from stream {self.config.stream_id}: {e}")
            self.status = StreamStatus.ERROR
            self.metrics.error_count += 1
            
            # Attempt reconnection
            if self.config.reconnect_attempts > 0:
                self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages."""
        while self.status == StreamStatus.CONNECTED:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                if self.websocket:
                    await self.websocket.ping()
                    self._last_heartbeat = time.time()
                    
            except Exception as e:
                logger.warning(f"Heartbeat failed for stream {self.config.stream_id}: {e}")
                break
    
    async def _reconnect(self):
        """Attempt to reconnect to the stream."""
        self.status = StreamStatus.RECONNECTING
        delay = self.config.reconnect_delay
        
        for attempt in range(self.config.reconnect_attempts):
            logger.info(f"Reconnection attempt {attempt + 1}/{self.config.reconnect_attempts} for stream {self.config.stream_id}")
            
            await asyncio.sleep(delay)
            
            if await self.connect():
                self.metrics.reconnection_count += 1
                return
                
            # Exponential backoff
            delay = min(delay * 2, self.config.max_reconnect_delay)
        
        logger.error(f"Failed to reconnect to stream {self.config.stream_id} after {self.config.reconnect_attempts} attempts")
        self.status = StreamStatus.ERROR


class StreamManager:
    """Manager for multiple real-time data streams with connection pooling."""
    
    def __init__(self):
        self.connections: Dict[str, StreamConnection] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._global_handlers: Set[Callable] = set()
        
    async def start(self):
        """Start the stream manager."""
        if self._running:
            return
            
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_connections())
        logger.info("Stream manager started")
    
    async def stop(self):
        """Stop the stream manager and all connections."""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            
        # Disconnect all streams
        for connection in self.connections.values():
            await connection.disconnect()
            
        self.connections.clear()
        logger.info("Stream manager stopped")
    
    async def add_stream(self, config: StreamConfig) -> bool:
        """Add a new stream connection."""
        if config.stream_id in self.connections:
            logger.warning(f"Stream {config.stream_id} already exists")
            return False
            
        connection = StreamConnection(config, self)
        
        # Add global handlers
        for handler in self._global_handlers:
            connection.add_handler(handler)
            
        self.connections[config.stream_id] = connection
        
        # Auto-connect if manager is running
        if self._running:
            return await connection.connect()
            
        return True
    
    async def remove_stream(self, stream_id: str):
        """Remove a stream connection."""
        if stream_id not in self.connections:
            logger.warning(f"Stream {stream_id} not found")
            return
            
        connection = self.connections[stream_id]
        await connection.disconnect()
        del self.connections[stream_id]
        logger.info(f"Removed stream {stream_id}")
    
    def add_global_handler(self, handler: Callable[[str, Dict[str, Any]], None]):
        """Add a global message handler for all streams."""
        self._global_handlers.add(handler)
        
        # Add to existing connections
        for connection in self.connections.values():
            connection.add_handler(lambda data, sid=connection.config.stream_id: handler(sid, data))
    
    def remove_global_handler(self, handler: Callable[[str, Dict[str, Any]], None]):
        """Remove a global message handler."""
        self._global_handlers.discard(handler)
    
    def get_stream_status(self, stream_id: str) -> Optional[StreamStatus]:
        """Get status of a specific stream."""
        connection = self.connections.get(stream_id)
        return connection.status if connection else None
    
    def get_stream_metrics(self, stream_id: str) -> Optional[StreamMetrics]:
        """Get metrics for a specific stream."""
        connection = self.connections.get(stream_id)
        return connection.metrics if connection else None
    
    def get_all_metrics(self) -> Dict[str, StreamMetrics]:
        """Get metrics for all streams."""
        return {
            stream_id: connection.metrics 
            for stream_id, connection in self.connections.items()
        }
    
    async def send_to_stream(self, stream_id: str, message: Dict[str, Any]):
        """Send message to a specific stream."""
        connection = self.connections.get(stream_id)
        if connection:
            await connection.send_message(message)
        else:
            logger.warning(f"Stream {stream_id} not found")
    
    async def _monitor_connections(self):
        """Monitor stream connections and handle reconnections."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                for stream_id, connection in self.connections.items():
                    # Check for stale connections
                    if connection.status == StreamStatus.CONNECTED:
                        time_since_heartbeat = time.time() - connection._last_heartbeat
                        if time_since_heartbeat > connection.config.heartbeat_interval * 3:
                            logger.warning(f"Stream {stream_id} appears stale, attempting reconnection")
                            asyncio.create_task(connection._reconnect())
                            
            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")

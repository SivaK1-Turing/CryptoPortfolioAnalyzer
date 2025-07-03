"""FastAPI WebSocket server for real-time portfolio monitoring."""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import uuid
import weakref

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PRICE_UPDATE = "price_update"
    PORTFOLIO_UPDATE = "portfolio_update"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    STATUS = "status"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    
    type: MessageType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_id: Optional[str] = None
    room: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "client_id": self.client_id,
            "room": self.room
        }


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client."""
    
    client_id: str
    websocket: WebSocket
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    async def send_message(self, message: WebSocketMessage):
        """Send message to this client."""
        try:
            message.client_id = self.client_id
            await self.websocket.send_text(json.dumps(message.to_dict()))
        except Exception as e:
            logger.error(f"Failed to send message to client {self.client_id}: {e}")
            raise
    
    async def send_error(self, error_message: str, error_code: str = "GENERAL_ERROR"):
        """Send error message to client."""
        error_msg = WebSocketMessage(
            type=MessageType.ERROR,
            data={"message": error_message, "code": error_code}
        )
        await self.send_message(error_msg)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self.connections: Dict[str, ClientConnection] = {}
        self.rooms: Dict[str, Set[str]] = {}  # room_name -> set of client_ids
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the connection manager."""
        if self._running:
            return
            
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Connection manager started")
    
    async def stop(self):
        """Stop the connection manager."""
        if not self._running:
            return
            
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        # Disconnect all clients
        for client in list(self.connections.values()):
            await self.disconnect_client(client.client_id)
            
        logger.info("Connection manager stopped")
    
    async def connect_client(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Connect a new WebSocket client."""
        if not client_id:
            client_id = str(uuid.uuid4())
            
        await websocket.accept()
        
        client = ClientConnection(
            client_id=client_id,
            websocket=websocket
        )
        
        self.connections[client_id] = client
        logger.info(f"Client {client_id} connected")
        
        # Send welcome message
        welcome_msg = WebSocketMessage(
            type=MessageType.STATUS,
            data={"status": "connected", "client_id": client_id}
        )
        await client.send_message(welcome_msg)
        
        return client_id
    
    async def disconnect_client(self, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id not in self.connections:
            return
            
        client = self.connections[client_id]
        
        # Remove from all rooms
        for room_name in list(client.subscriptions):
            await self.leave_room(client_id, room_name)
            
        # Close WebSocket connection
        try:
            await client.websocket.close()
        except Exception:
            pass  # Connection might already be closed
            
        del self.connections[client_id]
        logger.info(f"Client {client_id} disconnected")
    
    async def join_room(self, client_id: str, room_name: str):
        """Add client to a room for targeted broadcasting."""
        if client_id not in self.connections:
            logger.warning(f"Client {client_id} not found")
            return
            
        client = self.connections[client_id]
        client.subscriptions.add(room_name)
        
        if room_name not in self.rooms:
            self.rooms[room_name] = set()
        self.rooms[room_name].add(client_id)
        
        logger.debug(f"Client {client_id} joined room {room_name}")
    
    async def leave_room(self, client_id: str, room_name: str):
        """Remove client from a room."""
        if client_id not in self.connections:
            return
            
        client = self.connections[client_id]
        client.subscriptions.discard(room_name)
        
        if room_name in self.rooms:
            self.rooms[room_name].discard(client_id)
            if not self.rooms[room_name]:
                del self.rooms[room_name]
                
        logger.debug(f"Client {client_id} left room {room_name}")
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage):
        """Send message to a specific client."""
        if client_id not in self.connections:
            logger.warning(f"Client {client_id} not found")
            return
            
        client = self.connections[client_id]
        try:
            await client.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            await self.disconnect_client(client_id)
    
    async def broadcast_to_room(self, room_name: str, message: WebSocketMessage):
        """Broadcast message to all clients in a room."""
        if room_name not in self.rooms:
            logger.debug(f"Room {room_name} not found")
            return
            
        message.room = room_name
        disconnected_clients = []
        
        for client_id in self.rooms[room_name].copy():
            try:
                await self.send_to_client(client_id, message)
            except Exception:
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect_client(client_id)
    
    async def broadcast_to_all(self, message: WebSocketMessage):
        """Broadcast message to all connected clients."""
        disconnected_clients = []
        
        for client_id in list(self.connections.keys()):
            try:
                await self.send_to_client(client_id, message)
            except Exception:
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect_client(client_id)
    
    def get_client_count(self) -> int:
        """Get total number of connected clients."""
        return len(self.connections)
    
    def get_room_client_count(self, room_name: str) -> int:
        """Get number of clients in a specific room."""
        return len(self.rooms.get(room_name, set()))
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific client."""
        if client_id not in self.connections:
            return None
            
        client = self.connections[client_id]
        return {
            "client_id": client.client_id,
            "connected_at": client.connected_at.isoformat(),
            "last_heartbeat": client.last_heartbeat.isoformat(),
            "subscriptions": list(client.subscriptions),
            "metadata": client.metadata
        }
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages to all clients."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
                heartbeat_msg = WebSocketMessage(
                    type=MessageType.HEARTBEAT,
                    data={"timestamp": datetime.now(timezone.utc).isoformat()}
                )
                
                await self.broadcast_to_all(heartbeat_msg)
                
                # Check for stale connections
                current_time = datetime.now(timezone.utc)
                stale_clients = []
                
                for client_id, client in self.connections.items():
                    time_since_heartbeat = (current_time - client.last_heartbeat).total_seconds()
                    if time_since_heartbeat > 120:  # 2 minutes timeout
                        stale_clients.append(client_id)
                
                for client_id in stale_clients:
                    logger.warning(f"Disconnecting stale client {client_id}")
                    await self.disconnect_client(client_id)
                    
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")


class WebSocketServer:
    """FastAPI WebSocket server for real-time portfolio monitoring."""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Crypto Portfolio WebSocket Server")
        self.connection_manager = ConnectionManager()
        self._server_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
            """Main WebSocket endpoint."""
            client_id = await self.connection_manager.connect_client(websocket, client_id)
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Update client heartbeat
                    if client_id in self.connection_manager.connections:
                        self.connection_manager.connections[client_id].last_heartbeat = datetime.now(timezone.utc)
                    
                    # Handle message
                    await self._handle_client_message(client_id, message_data)
                    
            except WebSocketDisconnect:
                await self.connection_manager.disconnect_client(client_id)
            except Exception as e:
                logger.error(f"Error in WebSocket connection for client {client_id}: {e}")
                await self.connection_manager.disconnect_client(client_id)
        
        @self.app.get("/")
        async def get_dashboard():
            """Serve the main dashboard page."""
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Crypto Portfolio Dashboard</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                    .connected { background-color: #d4edda; color: #155724; }
                    .disconnected { background-color: #f8d7da; color: #721c24; }
                    #messages { height: 400px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px; }
                </style>
            </head>
            <body>
                <h1>Crypto Portfolio Dashboard</h1>
                <div id="status" class="status disconnected">Disconnected</div>
                <div>
                    <button onclick="subscribe('portfolio')">Subscribe to Portfolio</button>
                    <button onclick="subscribe('prices')">Subscribe to Prices</button>
                    <button onclick="unsubscribe('portfolio')">Unsubscribe Portfolio</button>
                    <button onclick="unsubscribe('prices')">Unsubscribe Prices</button>
                </div>
                <div id="messages"></div>
                
                <script>
                    const ws = new WebSocket('ws://localhost:8000/ws');
                    const status = document.getElementById('status');
                    const messages = document.getElementById('messages');
                    
                    ws.onopen = function(event) {
                        status.textContent = 'Connected';
                        status.className = 'status connected';
                    };
                    
                    ws.onclose = function(event) {
                        status.textContent = 'Disconnected';
                        status.className = 'status disconnected';
                    };
                    
                    ws.onmessage = function(event) {
                        const message = JSON.parse(event.data);
                        const div = document.createElement('div');
                        div.textContent = JSON.stringify(message, null, 2);
                        messages.appendChild(div);
                        messages.scrollTop = messages.scrollHeight;
                    };
                    
                    function subscribe(room) {
                        ws.send(JSON.stringify({type: 'subscribe', data: {room: room}}));
                    }
                    
                    function unsubscribe(room) {
                        ws.send(JSON.stringify({type: 'unsubscribe', data: {room: room}}));
                    }
                </script>
            </body>
            </html>
            """)
        
        @self.app.get("/status")
        async def get_server_status():
            """Get server status and statistics."""
            return {
                "status": "running" if self._running else "stopped",
                "connected_clients": self.connection_manager.get_client_count(),
                "rooms": {
                    room_name: self.connection_manager.get_room_client_count(room_name)
                    for room_name in self.connection_manager.rooms.keys()
                },
                "uptime": time.time() - getattr(self, '_start_time', time.time())
            }
    
    async def _handle_client_message(self, client_id: str, message_data: Dict[str, Any]):
        """Handle incoming message from client."""
        try:
            message_type = MessageType(message_data.get("type"))
            data = message_data.get("data", {})
            
            if message_type == MessageType.SUBSCRIBE:
                room = data.get("room")
                if room:
                    await self.connection_manager.join_room(client_id, room)
                    
            elif message_type == MessageType.UNSUBSCRIBE:
                room = data.get("room")
                if room:
                    await self.connection_manager.leave_room(client_id, room)
                    
            elif message_type == MessageType.HEARTBEAT:
                # Client heartbeat - already handled above
                pass
                
            else:
                logger.warning(f"Unknown message type from client {client_id}: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            
            # Send error response
            if client_id in self.connection_manager.connections:
                client = self.connection_manager.connections[client_id]
                await client.send_error(f"Error processing message: {str(e)}")
    
    async def start(self):
        """Start the WebSocket server."""
        if self._running:
            return
            
        self._running = True
        self._start_time = time.time()
        
        await self.connection_manager.start()
        
        # Start server in background
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        
        logger.info(f"WebSocket server started on {self.host}:{self.port}")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return
            
        self._running = False
        
        await self.connection_manager.stop()
        
        if self._server_task:
            self._server_task.cancel()
            
        logger.info("WebSocket server stopped")
    
    async def broadcast_price_update(self, symbol: str, price_data: Dict[str, Any]):
        """Broadcast price update to subscribed clients."""
        message = WebSocketMessage(
            type=MessageType.PRICE_UPDATE,
            data={"symbol": symbol, **price_data}
        )
        await self.connection_manager.broadcast_to_room("prices", message)
    
    async def broadcast_portfolio_update(self, portfolio_data: Dict[str, Any]):
        """Broadcast portfolio update to subscribed clients."""
        message = WebSocketMessage(
            type=MessageType.PORTFOLIO_UPDATE,
            data=portfolio_data
        )
        await self.connection_manager.broadcast_to_room("portfolio", message)
    
    async def send_alert(self, alert_data: Dict[str, Any], room: Optional[str] = None):
        """Send alert to clients."""
        message = WebSocketMessage(
            type=MessageType.ALERT,
            data=alert_data
        )
        
        if room:
            await self.connection_manager.broadcast_to_room(room, message)
        else:
            await self.connection_manager.broadcast_to_all(message)

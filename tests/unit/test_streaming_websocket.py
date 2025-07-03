"""Tests for the WebSocket server."""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from crypto_portfolio_analyzer.streaming.websocket_server import (
    WebSocketServer, ConnectionManager, ClientConnection, WebSocketMessage, MessageType
)


class TestWebSocketMessage:
    """Test WebSocketMessage dataclass."""
    
    def test_message_creation(self):
        """Test creating a WebSocket message."""
        message = WebSocketMessage(
            type=MessageType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000},
            client_id="test_client",
            room="prices"
        )
        
        assert message.type == MessageType.PRICE_UPDATE
        assert message.data == {"symbol": "BTC", "price": 50000}
        assert message.client_id == "test_client"
        assert message.room == "prices"
        assert isinstance(message.timestamp, datetime)
    
    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        message = WebSocketMessage(
            type=MessageType.ALERT,
            data={"message": "Test alert"},
            client_id="test_client"
        )
        
        result = message.to_dict()
        
        assert result["type"] == "alert"
        assert result["data"] == {"message": "Test alert"}
        assert result["client_id"] == "test_client"
        assert "timestamp" in result
        assert result["room"] is None


class TestClientConnection:
    """Test ClientConnection class."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        return AsyncMock()
    
    def test_client_creation(self, mock_websocket):
        """Test creating a client connection."""
        client = ClientConnection(
            client_id="test_client",
            websocket=mock_websocket
        )
        
        assert client.client_id == "test_client"
        assert client.websocket == mock_websocket
        assert len(client.subscriptions) == 0
        assert isinstance(client.connected_at, datetime)
        assert isinstance(client.last_heartbeat, datetime)
        assert client.metadata == {}
    
    async def test_send_message(self, mock_websocket):
        """Test sending a message to client."""
        client = ClientConnection(
            client_id="test_client",
            websocket=mock_websocket
        )
        
        message = WebSocketMessage(
            type=MessageType.STATUS,
            data={"status": "connected"}
        )
        
        await client.send_message(message)
        
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        sent_data = json.loads(call_args)
        
        assert sent_data["type"] == "status"
        assert sent_data["data"] == {"status": "connected"}
        assert sent_data["client_id"] == "test_client"
    
    async def test_send_error(self, mock_websocket):
        """Test sending an error message to client."""
        client = ClientConnection(
            client_id="test_client",
            websocket=mock_websocket
        )
        
        await client.send_error("Test error", "TEST_ERROR")
        
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        sent_data = json.loads(call_args)
        
        assert sent_data["type"] == "error"
        assert sent_data["data"]["message"] == "Test error"
        assert sent_data["data"]["code"] == "TEST_ERROR"


@pytest.mark.asyncio
class TestConnectionManager:
    """Test ConnectionManager class."""
    
    @pytest.fixture
    def connection_manager(self):
        """Create a connection manager."""
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        return AsyncMock()
    
    def test_connection_manager_creation(self, connection_manager):
        """Test creating a connection manager."""
        assert len(connection_manager.connections) == 0
        assert len(connection_manager.rooms) == 0
        assert connection_manager._heartbeat_task is None
        assert not connection_manager._running
    
    async def test_start_stop(self, connection_manager):
        """Test starting and stopping the connection manager."""
        assert not connection_manager._running
        
        await connection_manager.start()
        assert connection_manager._running
        assert connection_manager._heartbeat_task is not None
        
        await connection_manager.stop()
        assert not connection_manager._running
        assert len(connection_manager.connections) == 0
    
    async def test_connect_client(self, connection_manager, mock_websocket):
        """Test connecting a client."""
        client_id = await connection_manager.connect_client(mock_websocket)
        
        assert client_id in connection_manager.connections
        assert len(connection_manager.connections) == 1
        
        client = connection_manager.connections[client_id]
        assert client.client_id == client_id
        assert client.websocket == mock_websocket
        
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called_once()  # Welcome message
    
    async def test_connect_client_with_id(self, connection_manager, mock_websocket):
        """Test connecting a client with specific ID."""
        client_id = await connection_manager.connect_client(mock_websocket, "custom_id")
        
        assert client_id == "custom_id"
        assert "custom_id" in connection_manager.connections
    
    async def test_disconnect_client(self, connection_manager, mock_websocket):
        """Test disconnecting a client."""
        client_id = await connection_manager.connect_client(mock_websocket)
        assert client_id in connection_manager.connections
        
        await connection_manager.disconnect_client(client_id)
        assert client_id not in connection_manager.connections
        
        mock_websocket.close.assert_called_once()
    
    async def test_join_leave_room(self, connection_manager, mock_websocket):
        """Test joining and leaving rooms."""
        client_id = await connection_manager.connect_client(mock_websocket)
        
        # Join room
        await connection_manager.join_room(client_id, "test_room")
        
        assert "test_room" in connection_manager.rooms
        assert client_id in connection_manager.rooms["test_room"]
        
        client = connection_manager.connections[client_id]
        assert "test_room" in client.subscriptions
        
        # Leave room
        await connection_manager.leave_room(client_id, "test_room")
        
        assert "test_room" not in connection_manager.rooms
        assert "test_room" not in client.subscriptions
    
    async def test_send_to_client(self, connection_manager, mock_websocket):
        """Test sending message to specific client."""
        client_id = await connection_manager.connect_client(mock_websocket)
        
        message = WebSocketMessage(
            type=MessageType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000}
        )
        
        await connection_manager.send_to_client(client_id, message)
        
        # Should have been called twice: welcome message + our message
        assert mock_websocket.send_text.call_count == 2
    
    async def test_broadcast_to_room(self, connection_manager):
        """Test broadcasting to a room."""
        # Create multiple clients
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        
        client1 = await connection_manager.connect_client(mock_ws1)
        client2 = await connection_manager.connect_client(mock_ws2)
        client3 = await connection_manager.connect_client(mock_ws3)
        
        # Add clients to room
        await connection_manager.join_room(client1, "test_room")
        await connection_manager.join_room(client2, "test_room")
        # client3 not in room
        
        message = WebSocketMessage(
            type=MessageType.ALERT,
            data={"message": "Test broadcast"}
        )
        
        await connection_manager.broadcast_to_room("test_room", message)
        
        # Only clients in room should receive the message
        # (plus welcome messages)
        assert mock_ws1.send_text.call_count == 2
        assert mock_ws2.send_text.call_count == 2
        assert mock_ws3.send_text.call_count == 1  # Only welcome message
    
    async def test_broadcast_to_all(self, connection_manager):
        """Test broadcasting to all clients."""
        # Create multiple clients
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await connection_manager.connect_client(mock_ws1)
        await connection_manager.connect_client(mock_ws2)
        
        message = WebSocketMessage(
            type=MessageType.STATUS,
            data={"status": "maintenance"}
        )
        
        await connection_manager.broadcast_to_all(message)
        
        # All clients should receive the message (plus welcome messages)
        assert mock_ws1.send_text.call_count == 2
        assert mock_ws2.send_text.call_count == 2
    
    def test_get_client_count(self, connection_manager):
        """Test getting client count."""
        assert connection_manager.get_client_count() == 0
        
        # This would normally add clients, but we'll just modify directly for testing
        connection_manager.connections["client1"] = Mock()
        connection_manager.connections["client2"] = Mock()
        
        assert connection_manager.get_client_count() == 2
    
    def test_get_room_client_count(self, connection_manager):
        """Test getting room client count."""
        assert connection_manager.get_room_client_count("test_room") == 0
        
        # Add room with clients
        connection_manager.rooms["test_room"] = {"client1", "client2"}
        
        assert connection_manager.get_room_client_count("test_room") == 2
    
    async def test_get_client_info(self, connection_manager, mock_websocket):
        """Test getting client information."""
        # Non-existent client
        info = connection_manager.get_client_info("nonexistent")
        assert info is None
        
        # Existing client
        client_id = await connection_manager.connect_client(mock_websocket)
        info = connection_manager.get_client_info(client_id)
        
        assert info is not None
        assert info["client_id"] == client_id
        assert "connected_at" in info
        assert "last_heartbeat" in info
        assert "subscriptions" in info
        assert "metadata" in info


@pytest.mark.asyncio
class TestWebSocketServer:
    """Test WebSocketServer class."""
    
    @pytest.fixture
    def websocket_server(self):
        """Create a WebSocket server."""
        return WebSocketServer(host="localhost", port=8001)
    
    def test_websocket_server_creation(self, websocket_server):
        """Test creating a WebSocket server."""
        assert websocket_server.host == "localhost"
        assert websocket_server.port == 8001
        assert websocket_server.app is not None
        assert isinstance(websocket_server.connection_manager, ConnectionManager)
        assert websocket_server._server_task is None
        assert not websocket_server._running
    
    async def test_broadcast_price_update(self, websocket_server):
        """Test broadcasting price update."""
        # Mock the connection manager
        websocket_server.connection_manager.broadcast_to_room = AsyncMock()
        
        price_data = {"price": 50000, "change": 2.5}
        await websocket_server.broadcast_price_update("BTC", price_data)
        
        websocket_server.connection_manager.broadcast_to_room.assert_called_once()
        call_args = websocket_server.connection_manager.broadcast_to_room.call_args
        
        assert call_args[0][0] == "prices"  # room name
        message = call_args[0][1]  # message
        assert message.type == MessageType.PRICE_UPDATE
        assert message.data["symbol"] == "BTC"
        assert message.data["price"] == 50000
    
    async def test_broadcast_portfolio_update(self, websocket_server):
        """Test broadcasting portfolio update."""
        websocket_server.connection_manager.broadcast_to_room = AsyncMock()
        
        portfolio_data = {"total_value": 100000, "holdings": {}}
        await websocket_server.broadcast_portfolio_update(portfolio_data)
        
        websocket_server.connection_manager.broadcast_to_room.assert_called_once()
        call_args = websocket_server.connection_manager.broadcast_to_room.call_args
        
        assert call_args[0][0] == "portfolio"  # room name
        message = call_args[0][1]  # message
        assert message.type == MessageType.PORTFOLIO_UPDATE
        assert message.data == portfolio_data
    
    async def test_send_alert(self, websocket_server):
        """Test sending alert."""
        websocket_server.connection_manager.broadcast_to_room = AsyncMock()
        websocket_server.connection_manager.broadcast_to_all = AsyncMock()
        
        alert_data = {"message": "Price alert", "severity": "warning"}
        
        # Send to specific room
        await websocket_server.send_alert(alert_data, room="alerts")
        websocket_server.connection_manager.broadcast_to_room.assert_called_once()
        
        # Send to all clients
        await websocket_server.send_alert(alert_data)
        websocket_server.connection_manager.broadcast_to_all.assert_called_once()


@pytest.mark.asyncio
class TestWebSocketServerIntegration:
    """Integration tests for WebSocket server."""
    
    async def test_server_lifecycle(self):
        """Test server start and stop lifecycle."""
        server = WebSocketServer(host="localhost", port=8002)
        
        assert not server._running
        
        # Note: We can't easily test the actual server start without
        # running a real server, so we'll test the setup
        assert server.app is not None
        assert server.connection_manager is not None
        
        # Test that routes are set up
        routes = [route.path for route in server.app.routes]
        assert "/ws" in routes
        assert "/" in routes
        assert "/status" in routes

"""Tests for the streaming manager."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from crypto_portfolio_analyzer.streaming.manager import (
    StreamManager, StreamConfig, StreamConnection, StreamStatus, StreamMetrics
)


class TestStreamConfig:
    """Test StreamConfig dataclass."""
    
    def test_stream_config_creation(self):
        """Test creating a stream configuration."""
        config = StreamConfig(
            stream_id="test_stream",
            url="wss://example.com/ws",
            symbols=["BTC", "ETH"],
            reconnect_attempts=3,
            heartbeat_interval=30.0
        )
        
        assert config.stream_id == "test_stream"
        assert config.url == "wss://example.com/ws"
        assert config.symbols == ["BTC", "ETH"]
        assert config.reconnect_attempts == 3
        assert config.heartbeat_interval == 30.0
        assert config.buffer_size == 1000  # default
    
    def test_stream_config_defaults(self):
        """Test default values in stream configuration."""
        config = StreamConfig(
            stream_id="test",
            url="wss://example.com"
        )
        
        assert config.symbols == []
        assert config.reconnect_attempts == 5
        assert config.reconnect_delay == 1.0
        assert config.max_reconnect_delay == 60.0
        assert config.heartbeat_interval == 30.0
        assert config.buffer_size == 1000
        assert config.rate_limit is None
        assert config.headers == {}
        assert config.params == {}


class TestStreamMetrics:
    """Test StreamMetrics dataclass."""
    
    def test_stream_metrics_creation(self):
        """Test creating stream metrics."""
        metrics = StreamMetrics()
        
        assert metrics.messages_received == 0
        assert metrics.messages_sent == 0
        assert metrics.bytes_received == 0
        assert metrics.bytes_sent == 0
        assert metrics.connection_count == 0
        assert metrics.reconnection_count == 0
        assert metrics.error_count == 0
        assert metrics.last_message_time is None
        assert metrics.uptime_seconds == 0.0
        assert metrics.latency_ms == 0.0


class TestStreamConnection:
    """Test StreamConnection class."""

    @pytest.fixture
    def stream_config(self):
        """Create a test stream configuration."""
        return StreamConfig(
            stream_id="test_stream",
            url="wss://example.com/ws",
            symbols=["BTC"],
            reconnect_attempts=2,
            heartbeat_interval=10.0
        )

    @pytest.fixture
    def mock_manager(self):
        """Create a mock stream manager."""
        manager = Mock()
        return manager

    def test_stream_connection_creation(self, stream_config, mock_manager):
        """Test creating a stream connection."""
        connection = StreamConnection(stream_config, mock_manager)
        
        assert connection.config == stream_config
        assert connection.status == StreamStatus.DISCONNECTED
        assert connection.websocket is None
        assert isinstance(connection.metrics, StreamMetrics)
        assert connection._reconnect_task is None
        assert connection._heartbeat_task is None
    
    @pytest.mark.asyncio
    async def test_connect_success(self, stream_config, mock_manager):
        """Test successful connection."""
        mock_websocket = AsyncMock()
        mock_websockets_module = Mock()
        mock_websockets_module.connect = AsyncMock(return_value=mock_websocket)

        connection = StreamConnection(stream_config, mock_manager)

        # Mock the local import of websockets
        with patch('builtins.__import__', side_effect=lambda name, *args: mock_websockets_module if name == 'websockets' else __import__(name, *args)):
            result = await connection.connect()

        assert result is True
        assert connection.status == StreamStatus.CONNECTED
        assert connection.websocket == mock_websocket
        assert connection.metrics.connection_count == 1
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, stream_config, mock_manager):
        """Test connection failure."""
        mock_websockets_module = Mock()
        mock_websockets_module.connect = AsyncMock(side_effect=Exception("Connection failed"))

        connection = StreamConnection(stream_config, mock_manager)

        # Mock the local import of websockets to raise an exception
        with patch('builtins.__import__', side_effect=lambda name, *args: mock_websockets_module if name == 'websockets' else __import__(name, *args)):
            result = await connection.connect()

        assert result is False
        assert connection.status == StreamStatus.ERROR
        assert connection.websocket is None
        assert connection.metrics.error_count == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, stream_config, mock_manager):
        """Test disconnection."""
        connection = StreamConnection(stream_config, mock_manager)
        mock_websocket = AsyncMock()
        connection.websocket = mock_websocket
        connection.status = StreamStatus.CONNECTED
        connection._connection_start_time = 1000.0

        with patch('time.time', return_value=1010.0):
            await connection.disconnect()

        assert connection.status == StreamStatus.DISCONNECTED
        assert connection.websocket is None
        assert connection.metrics.uptime_seconds == 10.0
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, stream_config, mock_manager):
        """Test sending message successfully."""
        connection = StreamConnection(stream_config, mock_manager)
        connection.websocket = AsyncMock()
        connection.status = StreamStatus.CONNECTED

        message = {"type": "test", "data": "hello"}
        await connection.send_message(message)

        connection.websocket.send.assert_called_once()
        assert connection.metrics.messages_sent == 1
        assert connection.metrics.bytes_sent > 0

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, stream_config, mock_manager):
        """Test sending message when not connected."""
        connection = StreamConnection(stream_config, mock_manager)
        connection.status = StreamStatus.DISCONNECTED

        message = {"type": "test", "data": "hello"}
        await connection.send_message(message)

        assert connection.metrics.messages_sent == 0
    
    def test_add_remove_handler(self, stream_config, mock_manager):
        """Test adding and removing message handlers."""
        connection = StreamConnection(stream_config, mock_manager)

        handler1 = Mock()
        handler2 = Mock()

        # Add handlers
        connection.add_handler(handler1)
        connection.add_handler(handler2)

        assert len(connection._handlers) == 2
        assert handler1 in connection._handlers
        assert handler2 in connection._handlers

        # Remove handler
        connection.remove_handler(handler1)

        assert len(connection._handlers) == 1
        assert handler1 not in connection._handlers
        assert handler2 in connection._handlers


class TestStreamManager:
    """Test StreamManager class."""
    
    @pytest.fixture
    def stream_manager(self):
        """Create a stream manager."""
        return StreamManager()
    
    @pytest.fixture
    def stream_config(self):
        """Create a test stream configuration."""
        return StreamConfig(
            stream_id="test_stream",
            url="wss://example.com/ws",
            symbols=["BTC"]
        )
    
    def test_stream_manager_creation(self, stream_manager):
        """Test creating a stream manager."""
        assert len(stream_manager.connections) == 0
        assert stream_manager._running is False
        assert stream_manager._monitor_task is None
        assert len(stream_manager._global_handlers) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop(self, stream_manager):
        """Test starting and stopping the stream manager."""
        assert not stream_manager._running

        await stream_manager.start()
        assert stream_manager._running
        assert stream_manager._monitor_task is not None

        await stream_manager.stop()
        assert not stream_manager._running
        assert len(stream_manager.connections) == 0

    @pytest.mark.asyncio
    async def test_add_stream(self, stream_manager, stream_config):
        """Test adding a stream."""
        result = await stream_manager.add_stream(stream_config)

        assert result is True
        assert stream_config.stream_id in stream_manager.connections

        connection = stream_manager.connections[stream_config.stream_id]
        assert connection.config == stream_config

    @pytest.mark.asyncio
    async def test_add_duplicate_stream(self, stream_manager, stream_config):
        """Test adding a duplicate stream."""
        await stream_manager.add_stream(stream_config)
        result = await stream_manager.add_stream(stream_config)

        assert result is False
        assert len(stream_manager.connections) == 1

    @pytest.mark.asyncio
    async def test_remove_stream(self, stream_manager, stream_config):
        """Test removing a stream."""
        await stream_manager.add_stream(stream_config)
        assert stream_config.stream_id in stream_manager.connections

        await stream_manager.remove_stream(stream_config.stream_id)
        assert stream_config.stream_id not in stream_manager.connections

    @pytest.mark.asyncio
    async def test_remove_nonexistent_stream(self, stream_manager):
        """Test removing a non-existent stream."""
        # Should not raise an exception
        await stream_manager.remove_stream("nonexistent")
    
    def test_add_global_handler(self, stream_manager):
        """Test adding a global handler."""
        handler = Mock()

        stream_manager.add_global_handler(handler)
        assert handler in stream_manager._global_handlers

    def test_remove_global_handler(self, stream_manager):
        """Test removing a global handler."""
        handler = Mock()

        stream_manager.add_global_handler(handler)
        assert handler in stream_manager._global_handlers

        stream_manager.remove_global_handler(handler)
        assert handler not in stream_manager._global_handlers
    
    @pytest.mark.asyncio
    async def test_get_stream_status(self, stream_manager, stream_config):
        """Test getting stream status."""
        # Non-existent stream
        status = stream_manager.get_stream_status("nonexistent")
        assert status is None

        # Existing stream
        await stream_manager.add_stream(stream_config)
        status = stream_manager.get_stream_status(stream_config.stream_id)
        assert status == StreamStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_stream_metrics(self, stream_manager, stream_config):
        """Test getting stream metrics."""
        # Non-existent stream
        metrics = stream_manager.get_stream_metrics("nonexistent")
        assert metrics is None

        # Existing stream
        await stream_manager.add_stream(stream_config)
        metrics = stream_manager.get_stream_metrics(stream_config.stream_id)
        assert isinstance(metrics, StreamMetrics)

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, stream_manager, stream_config):
        """Test getting all stream metrics."""
        metrics = stream_manager.get_all_metrics()
        assert metrics == {}

        await stream_manager.add_stream(stream_config)
        metrics = stream_manager.get_all_metrics()
        assert stream_config.stream_id in metrics
        assert isinstance(metrics[stream_config.stream_id], StreamMetrics)

    @pytest.mark.asyncio
    async def test_send_to_stream(self, stream_manager, stream_config):
        """Test sending message to a specific stream."""
        await stream_manager.add_stream(stream_config)

        connection = stream_manager.connections[stream_config.stream_id]
        connection.send_message = AsyncMock()

        message = {"type": "test"}
        await stream_manager.send_to_stream(stream_config.stream_id, message)

        connection.send_message.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_stream(self, stream_manager):
        """Test sending message to non-existent stream."""
        # Should not raise an exception
        await stream_manager.send_to_stream("nonexistent", {"type": "test"})


class TestStreamManagerIntegration:
    """Integration tests for StreamManager."""

    @pytest.mark.asyncio
    async def test_manager_with_multiple_streams(self):
        """Test manager with multiple streams."""
        manager = StreamManager()

        config1 = StreamConfig(stream_id="stream1", url="wss://example1.com")
        config2 = StreamConfig(stream_id="stream2", url="wss://example2.com")

        await manager.add_stream(config1)
        await manager.add_stream(config2)

        assert len(manager.connections) == 2
        assert "stream1" in manager.connections
        assert "stream2" in manager.connections

        # Test metrics
        all_metrics = manager.get_all_metrics()
        assert len(all_metrics) == 2

        # Cleanup
        await manager.stop()

    @pytest.mark.asyncio
    async def test_global_handlers_applied_to_new_streams(self):
        """Test that global handlers are applied to new streams."""
        manager = StreamManager()
        handler = Mock()

        # Add global handler before adding streams
        manager.add_global_handler(handler)

        config = StreamConfig(stream_id="test", url="wss://example.com")
        await manager.add_stream(config)

        connection = manager.connections["test"]
        # Global handler should be added to the connection
        # (This is a simplified test - in practice, the handler would be wrapped)
        assert len(connection._handlers) > 0

        await manager.stop()

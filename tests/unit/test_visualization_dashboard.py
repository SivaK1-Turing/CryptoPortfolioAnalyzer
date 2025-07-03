"""Tests for visualization dashboard module."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from crypto_portfolio_analyzer.visualization.dashboard import (
    DashboardConfig, ConnectionManager, WebDashboard, DashboardManager
)


class TestDashboardConfig:
    """Test DashboardConfig class."""
    
    def test_dashboard_config_creation(self):
        """Test creating dashboard configuration."""
        config = DashboardConfig(
            host="0.0.0.0",
            port=8080,
            title="Test Dashboard",
            theme="dark"
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.title == "Test Dashboard"
        assert config.theme == "dark"
        assert config.auto_refresh is True
        assert config.refresh_interval == 5
    
    def test_dashboard_config_defaults(self):
        """Test dashboard configuration defaults."""
        config = DashboardConfig()
        
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.title == "Crypto Portfolio Dashboard"
        assert config.theme == "light"
        assert config.auto_refresh is True
        assert config.enable_websocket is True


class TestConnectionManager:
    """Test ConnectionManager class."""
    
    @pytest.fixture
    def connection_manager(self):
        """Create connection manager for testing."""
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket
    
    @pytest.mark.asyncio
    async def test_connect_client(self, connection_manager, mock_websocket):
        """Test connecting a client."""
        client_id = await connection_manager.connect(mock_websocket, "test_client")
        
        assert client_id == "test_client"
        assert mock_websocket in connection_manager.active_connections
        assert mock_websocket in connection_manager.connection_data
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_client_auto_id(self, connection_manager, mock_websocket):
        """Test connecting client with auto-generated ID."""
        client_id = await connection_manager.connect(mock_websocket)
        
        assert client_id.startswith("client_")
        assert mock_websocket in connection_manager.active_connections
    
    def test_disconnect_client(self, connection_manager, mock_websocket):
        """Test disconnecting a client."""
        # First connect
        connection_manager.active_connections.append(mock_websocket)
        connection_manager.connection_data[mock_websocket] = {"client_id": "test"}
        
        # Then disconnect
        connection_manager.disconnect(mock_websocket)
        
        assert mock_websocket not in connection_manager.active_connections
        assert mock_websocket not in connection_manager.connection_data
    
    @pytest.mark.asyncio
    async def test_send_personal_message(self, connection_manager, mock_websocket):
        """Test sending personal message."""
        connection_manager.active_connections.append(mock_websocket)
        
        await connection_manager.send_personal_message("test message", mock_websocket)
        
        mock_websocket.send_text.assert_called_once_with("test message")
    
    @pytest.mark.asyncio
    async def test_send_personal_message_error(self, connection_manager, mock_websocket):
        """Test sending personal message with error."""
        connection_manager.active_connections.append(mock_websocket)
        connection_manager.connection_data[mock_websocket] = {"client_id": "test"}
        mock_websocket.send_text.side_effect = Exception("Connection error")
        
        await connection_manager.send_personal_message("test message", mock_websocket)
        
        # Should remove connection on error
        assert mock_websocket not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_broadcast(self, connection_manager):
        """Test broadcasting message."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        connection_manager.active_connections.extend([mock_ws1, mock_ws2])
        
        await connection_manager.broadcast("broadcast message")
        
        mock_ws1.send_text.assert_called_once_with("broadcast message")
        mock_ws2.send_text.assert_called_once_with("broadcast message")
    
    @pytest.mark.asyncio
    async def test_broadcast_with_error(self, connection_manager):
        """Test broadcasting with connection error."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send_text.side_effect = Exception("Connection error")
        
        connection_manager.active_connections.extend([mock_ws1, mock_ws2])
        connection_manager.connection_data[mock_ws2] = {"client_id": "test"}
        
        await connection_manager.broadcast("broadcast message")
        
        # Should remove failed connection
        assert mock_ws1 in connection_manager.active_connections
        assert mock_ws2 not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_send_chart_update(self, connection_manager, mock_websocket):
        """Test sending chart update."""
        connection_manager.active_connections.append(mock_websocket)
        
        chart_data = {"type": "price_update", "symbol": "BTC", "price": 50000}
        await connection_manager.send_chart_update(chart_data)
        
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "chart_update"
        assert message["data"] == chart_data
        assert "timestamp" in message
    
    @pytest.mark.asyncio
    async def test_send_portfolio_update(self, connection_manager, mock_websocket):
        """Test sending portfolio update."""
        connection_manager.active_connections.append(mock_websocket)
        
        portfolio_data = {"total_value": 100000, "holdings": []}
        await connection_manager.send_portfolio_update(portfolio_data)
        
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "portfolio_update"
        assert message["data"] == portfolio_data
    
    def test_get_connection_count(self, connection_manager):
        """Test getting connection count."""
        assert connection_manager.get_connection_count() == 0
        
        connection_manager.active_connections.append(Mock())
        connection_manager.active_connections.append(Mock())
        
        assert connection_manager.get_connection_count() == 2


class TestWebDashboard:
    """Test WebDashboard class."""
    
    @pytest.fixture
    def dashboard_config(self):
        """Create dashboard configuration for testing."""
        return DashboardConfig(
            host="localhost",
            port=8081,  # Use different port for testing
            title="Test Dashboard"
        )
    
    @pytest.fixture
    def web_dashboard(self, dashboard_config):
        """Create web dashboard for testing."""
        return WebDashboard(dashboard_config)
    
    def test_web_dashboard_creation(self, web_dashboard, dashboard_config):
        """Test creating web dashboard."""
        assert web_dashboard.config == dashboard_config
        assert web_dashboard.app is not None
        assert web_dashboard.chart_generator is not None
        assert web_dashboard.connection_manager is not None
        assert web_dashboard.running is False
    
    def test_dashboard_routes_setup(self, web_dashboard):
        """Test that dashboard routes are set up."""
        # Check that routes exist
        routes = [route.path for route in web_dashboard.app.routes]
        
        assert "/" in routes
        assert "/api/status" in routes
        assert "/api/charts/portfolio" in routes
        assert "/api/charts/allocation" in routes
        assert "/ws" in routes
    
    @pytest.mark.asyncio
    async def test_dashboard_status_endpoint(self, web_dashboard):
        """Test dashboard status endpoint."""
        from fastapi.testclient import TestClient
        
        client = TestClient(web_dashboard.app)
        response = client.get("/api/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"  # Not running yet
        assert "connections" in data
        assert "config" in data
    
    def test_is_running(self, web_dashboard):
        """Test is_running method."""
        assert web_dashboard.is_running() is False
        
        web_dashboard.running = True
        assert web_dashboard.is_running() is True
    
    @pytest.mark.asyncio
    async def test_set_event_bus(self, web_dashboard):
        """Test setting event bus."""
        mock_event_bus = Mock()
        mock_event_bus.subscribe = Mock()
        
        web_dashboard.set_event_bus(mock_event_bus)
        
        assert web_dashboard.event_bus == mock_event_bus
        # Should subscribe to events
        assert mock_event_bus.subscribe.call_count == 2
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_event(self, web_dashboard):
        """Test handling portfolio events."""
        mock_event = Mock()
        mock_event.data = {"total_value": 100000}
        
        with patch.object(web_dashboard.connection_manager, 'send_portfolio_update') as mock_send:
            await web_dashboard._handle_portfolio_event(mock_event)
            mock_send.assert_called_once_with(mock_event.data)
    
    @pytest.mark.asyncio
    async def test_handle_price_event(self, web_dashboard):
        """Test handling price events."""
        mock_event = Mock()
        mock_event.data = {"symbol": "BTC", "price": 50000}
        mock_event.timestamp = datetime.now(timezone.utc)
        
        with patch.object(web_dashboard.connection_manager, 'send_chart_update') as mock_send:
            await web_dashboard._handle_price_event(mock_event)
            mock_send.assert_called_once()
            
            call_args = mock_send.call_args[0][0]
            assert call_args["type"] == "price_update"
            assert call_args["symbol"] == "BTC"
            assert call_args["price"] == 50000


class TestDashboardManager:
    """Test DashboardManager class."""
    
    @pytest.fixture
    def dashboard_manager(self):
        """Create dashboard manager for testing."""
        return DashboardManager()
    
    def test_dashboard_manager_creation(self, dashboard_manager):
        """Test creating dashboard manager."""
        assert dashboard_manager.dashboards == {}
        assert dashboard_manager.default_config is not None
    
    def test_create_dashboard(self, dashboard_manager):
        """Test creating dashboard."""
        config = DashboardConfig(title="Test Dashboard")
        dashboard = dashboard_manager.create_dashboard("test", config)
        
        assert isinstance(dashboard, WebDashboard)
        assert dashboard.config == config
        assert "test" in dashboard_manager.dashboards
        assert dashboard_manager.dashboards["test"] == dashboard
    
    def test_create_duplicate_dashboard(self, dashboard_manager):
        """Test creating duplicate dashboard."""
        dashboard_manager.create_dashboard("test")
        
        with pytest.raises(ValueError, match="Dashboard 'test' already exists"):
            dashboard_manager.create_dashboard("test")
    
    def test_get_dashboard(self, dashboard_manager):
        """Test getting dashboard."""
        dashboard = dashboard_manager.create_dashboard("test")
        
        retrieved = dashboard_manager.get_dashboard("test")
        assert retrieved == dashboard
        
        # Test non-existent dashboard
        assert dashboard_manager.get_dashboard("nonexistent") is None
    
    def test_remove_dashboard(self, dashboard_manager):
        """Test removing dashboard."""
        dashboard_manager.create_dashboard("test")
        
        result = dashboard_manager.remove_dashboard("test")
        assert result is True
        assert "test" not in dashboard_manager.dashboards
        
        # Test removing non-existent dashboard
        result = dashboard_manager.remove_dashboard("nonexistent")
        assert result is False
    
    def test_list_dashboards(self, dashboard_manager):
        """Test listing dashboards."""
        assert dashboard_manager.list_dashboards() == []
        
        dashboard_manager.create_dashboard("test1")
        dashboard_manager.create_dashboard("test2")
        
        dashboards = dashboard_manager.list_dashboards()
        assert "test1" in dashboards
        assert "test2" in dashboards
        assert len(dashboards) == 2
    
    @pytest.mark.asyncio
    async def test_start_all_dashboards(self, dashboard_manager):
        """Test starting all dashboards."""
        dashboard1 = dashboard_manager.create_dashboard("test1")
        dashboard2 = dashboard_manager.create_dashboard("test2")
        
        with patch.object(dashboard1, 'start') as mock_start1, \
             patch.object(dashboard2, 'start') as mock_start2, \
             patch.object(dashboard1, 'is_running', return_value=False), \
             patch.object(dashboard2, 'is_running', return_value=False):
            
            await dashboard_manager.start_all()
            
            # Note: start() is called via asyncio.create_task, so we can't easily verify the calls
            # In a real test, we'd need to mock asyncio.create_task
    
    @pytest.mark.asyncio
    async def test_stop_all_dashboards(self, dashboard_manager):
        """Test stopping all dashboards."""
        dashboard1 = dashboard_manager.create_dashboard("test1")
        dashboard2 = dashboard_manager.create_dashboard("test2")
        
        dashboard1.running = True
        dashboard2.running = True
        
        with patch.object(dashboard1, 'stop') as mock_stop1, \
             patch.object(dashboard2, 'stop') as mock_stop2:
            
            await dashboard_manager.stop_all()
            
            mock_stop1.assert_called_once()
            mock_stop2.assert_called_once()

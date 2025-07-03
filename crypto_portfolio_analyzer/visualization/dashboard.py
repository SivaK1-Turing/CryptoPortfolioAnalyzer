"""Web dashboard server for real-time portfolio monitoring."""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import plotly
import plotly.graph_objects as go

from .charts import ChartGenerator, ChartConfig, ChartType
from ..streaming.events import StreamEventBus, EventType
from ..analytics.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    host: str = "localhost"
    port: int = 8080
    title: str = "Crypto Portfolio Dashboard"
    theme: str = "light"
    auto_refresh: bool = True
    refresh_interval: int = 5  # seconds
    enable_websocket: bool = True
    static_files_path: Optional[str] = None
    templates_path: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_data[websocket] = {
            'client_id': client_id or f"client_{len(self.active_connections)}",
            'connected_at': datetime.now(timezone.utc),
            'subscriptions': set()
        }
        logger.info(f"Client {client_id} connected to dashboard")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            client_data = self.connection_data.pop(websocket, {})
            client_id = client_data.get('client_id', 'unknown')
            logger.info(f"Client {client_id} disconnected from dashboard")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific client."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_chart_update(self, chart_data: Dict[str, Any]):
        """Send chart update to all connected clients."""
        message = json.dumps({
            'type': 'chart_update',
            'data': chart_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        await self.broadcast(message)

    async def send_portfolio_update(self, portfolio_data: Dict[str, Any]):
        """Send portfolio update to all connected clients."""
        message = json.dumps({
            'type': 'portfolio_update',
            'data': portfolio_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        await self.broadcast(message)

    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)


class WebDashboard:
    """FastAPI-based web dashboard for portfolio visualization."""

    def __init__(self, config: DashboardConfig):
        """Initialize web dashboard.

        Args:
            config: Dashboard configuration
        """
        self.config = config
        self.app = FastAPI(title=config.title)
        self.chart_generator = ChartGenerator()
        self.connection_manager = ConnectionManager()
        self.event_bus = None
        self.running = False

        # Setup routes
        self._setup_routes()

        # Setup static files and templates
        self._setup_static_files()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Dashboard home page."""
            return self._render_dashboard_template(request)

        @self.app.get("/api/status")
        async def get_status():
            """Get dashboard status."""
            return {
                "status": "running" if self.running else "stopped",
                "connections": self.connection_manager.get_connection_count(),
                "config": {
                    "title": self.config.title,
                    "theme": self.config.theme,
                    "auto_refresh": self.config.auto_refresh,
                    "refresh_interval": self.config.refresh_interval
                }
            }

        @self.app.get("/api/charts/portfolio")
        async def get_portfolio_chart():
            """Get portfolio performance chart."""
            # This would integrate with actual portfolio data
            # For now, return a placeholder
            return {"chart": "portfolio_chart_placeholder"}

        @self.app.get("/api/charts/allocation")
        async def get_allocation_chart():
            """Get portfolio allocation chart."""
            # This would integrate with actual portfolio data
            return {"chart": "allocation_chart_placeholder"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.connection_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)

                    # Handle different message types
                    if message.get('type') == 'subscribe':
                        # Handle subscription to specific data feeds
                        pass
                    elif message.get('type') == 'ping':
                        await websocket.send_text(json.dumps({'type': 'pong'}))

            except WebSocketDisconnect:
                self.connection_manager.disconnect(websocket)

    def _setup_static_files(self):
        """Setup static files and templates."""
        # In a full implementation, this would setup actual static files
        # For now, we'll create the basic structure
        pass

    def _render_dashboard_template(self, request: Request) -> HTMLResponse:
        """Render dashboard HTML template."""
        # Basic HTML template for the dashboard
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.config.title}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .header {{ background: #1f77b4; color: white; padding: 20px; margin: -20px -20px 20px -20px; }}
                .dashboard-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .chart-container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                .status {{ background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{self.config.title}</h1>
                <p>Real-time Portfolio Monitoring</p>
            </div>

            <div class="status">
                <strong>Status:</strong> <span id="status">Connected</span> |
                <strong>Last Update:</strong> <span id="last-update">-</span> |
                <strong>Connections:</strong> <span id="connections">0</span>
            </div>

            <div class="dashboard-grid">
                <div class="chart-container">
                    <h3>Portfolio Performance</h3>
                    <div id="portfolio-chart"></div>
                </div>

                <div class="chart-container">
                    <h3>Asset Allocation</h3>
                    <div id="allocation-chart"></div>
                </div>

                <div class="chart-container">
                    <h3>Price Charts</h3>
                    <div id="price-chart"></div>
                </div>

                <div class="chart-container">
                    <h3>Performance Metrics</h3>
                    <div id="metrics-chart"></div>
                </div>
            </div>

            <script>
                // WebSocket connection for real-time updates
                const ws = new WebSocket('ws://localhost:{self.config.port}/ws');

                ws.onopen = function(event) {{
                    console.log('Connected to dashboard WebSocket');
                    document.getElementById('status').textContent = 'Connected';
                }};

                ws.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);

                    if (data.type === 'chart_update') {{
                        updateCharts(data.data);
                    }} else if (data.type === 'portfolio_update') {{
                        updatePortfolio(data.data);
                    }}

                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                }};

                ws.onclose = function(event) {{
                    console.log('Disconnected from dashboard WebSocket');
                    document.getElementById('status').textContent = 'Disconnected';
                }};

                function updateCharts(chartData) {{
                    // Update charts with new data
                    console.log('Updating charts:', chartData);
                }}

                function updatePortfolio(portfolioData) {{
                    // Update portfolio display
                    console.log('Updating portfolio:', portfolioData);
                }}

                // Initialize placeholder charts
                Plotly.newPlot('portfolio-chart', [{{
                    x: [1, 2, 3, 4],
                    y: [10, 11, 12, 13],
                    type: 'scatter'
                }}], {{title: 'Portfolio Value'}});

                Plotly.newPlot('allocation-chart', [{{
                    values: [19, 26, 55],
                    labels: ['BTC', 'ETH', 'Others'],
                    type: 'pie'
                }}], {{title: 'Asset Allocation'}});
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    async def start(self):
        """Start the dashboard server."""
        self.running = True
        logger.info(f"Starting dashboard server on {self.config.host}:{self.config.port}")

        # Start the server
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self):
        """Stop the dashboard server."""
        self.running = False
        logger.info("Dashboard server stopped")

    def is_running(self) -> bool:
        """Check if dashboard is running."""
        return self.running

    def set_event_bus(self, event_bus: StreamEventBus):
        """Set event bus for real-time updates."""
        self.event_bus = event_bus
        # Subscribe to relevant events
        if event_bus:
            event_bus.subscribe(
                "dashboard_portfolio",
                self._handle_portfolio_event,
                event_types={EventType.PORTFOLIO_UPDATE}
            )
            event_bus.subscribe(
                "dashboard_price",
                self._handle_price_event,
                event_types={EventType.PRICE_UPDATE}
            )

    async def _handle_portfolio_event(self, event):
        """Handle portfolio update events."""
        await self.connection_manager.send_portfolio_update(event.data)

    async def _handle_price_event(self, event):
        """Handle price update events."""
        chart_data = {
            'type': 'price_update',
            'symbol': event.data.get('symbol'),
            'price': event.data.get('price'),
            'timestamp': event.timestamp.isoformat()
        }
        await self.connection_manager.send_chart_update(chart_data)


class DashboardManager:
    """Manages dashboard instances and lifecycle."""

    def __init__(self):
        """Initialize dashboard manager."""
        self.dashboards: Dict[str, WebDashboard] = {}
        self.default_config = DashboardConfig()

    def create_dashboard(self, name: str, config: Optional[DashboardConfig] = None) -> WebDashboard:
        """Create a new dashboard instance.

        Args:
            name: Dashboard name
            config: Dashboard configuration

        Returns:
            Dashboard instance
        """
        if name in self.dashboards:
            raise ValueError(f"Dashboard '{name}' already exists")

        dashboard_config = config or self.default_config
        dashboard = WebDashboard(dashboard_config)
        self.dashboards[name] = dashboard

        logger.info(f"Created dashboard '{name}'")
        return dashboard

    def get_dashboard(self, name: str) -> Optional[WebDashboard]:
        """Get dashboard by name.

        Args:
            name: Dashboard name

        Returns:
            Dashboard instance or None
        """
        return self.dashboards.get(name)

    def remove_dashboard(self, name: str) -> bool:
        """Remove dashboard.

        Args:
            name: Dashboard name

        Returns:
            True if removed, False if not found
        """
        if name in self.dashboards:
            dashboard = self.dashboards.pop(name)
            if dashboard.is_running():
                asyncio.create_task(dashboard.stop())
            logger.info(f"Removed dashboard '{name}'")
            return True
        return False

    def list_dashboards(self) -> List[str]:
        """List all dashboard names.

        Returns:
            List of dashboard names
        """
        return list(self.dashboards.keys())

    async def start_all(self):
        """Start all dashboards."""
        for name, dashboard in self.dashboards.items():
            if not dashboard.is_running():
                logger.info(f"Starting dashboard '{name}'")
                asyncio.create_task(dashboard.start())

    async def stop_all(self):
        """Stop all dashboards."""
        for name, dashboard in self.dashboards.items():
            if dashboard.is_running():
                logger.info(f"Stopping dashboard '{name}'")
                await dashboard.stop()


# Legacy compatibility
class DashboardServer(WebDashboard):
    """Legacy dashboard server class for backward compatibility."""

    def __init__(self):
        """Initialize legacy dashboard server."""
        config = DashboardConfig(port=8000)
        super().__init__(config)
        logger.info("Legacy dashboard server initialized")

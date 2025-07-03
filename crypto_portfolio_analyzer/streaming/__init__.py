"""Real-time data streaming module for cryptocurrency portfolio analysis.

This module provides comprehensive real-time data streaming capabilities including:
- WebSocket connections for live price feeds
- Stream management with connection pooling
- Event-driven updates and notifications
- Portfolio monitoring and alerts
- Real-time dashboard integration
"""

from .manager import StreamManager
from .websocket_server import WebSocketServer
from .price_feeds import PriceFeedManager
from .portfolio_monitor import PortfolioMonitor
from .events import StreamEventBus

__all__ = [
    'StreamManager',
    'WebSocketServer', 
    'PriceFeedManager',
    'PortfolioMonitor',
    'StreamEventBus'
]

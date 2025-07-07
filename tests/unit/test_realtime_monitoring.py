"""Unit tests for real-time monitoring features."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.streaming.realtime_tracker import (
    RealTimePortfolioTracker, TrackingConfig, TrackingMode, PortfolioMetrics
)
from crypto_portfolio_analyzer.streaming.alerts import (
    EnhancedAlertManager, Alert, AlertRule, AlertType, AlertSeverity,
    ConsoleNotificationHandler, NotificationConfig, NotificationChannel
)
from crypto_portfolio_analyzer.streaming.events import (
    StreamEvent, EventType, StreamEventBus
)
from crypto_portfolio_analyzer.analytics.models import PortfolioHolding


class TestPortfolioMetrics:
    """Test PortfolioMetrics class."""
    
    def test_portfolio_metrics_creation(self):
        """Test creating portfolio metrics."""
        metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=Decimal("67500"),
            total_cost=Decimal("60000"),
            total_return=Decimal("7500"),
            return_percentage=12.5,
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        assert metrics.total_value == Decimal("67500")
        assert metrics.total_cost == Decimal("60000")
        assert metrics.return_percentage == 12.5
        assert metrics.daily_pnl == Decimal("1000")
    
    def test_portfolio_metrics_serialization(self):
        """Test portfolio metrics to_dict method."""
        metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=Decimal("67500"),
            total_cost=Decimal("60000"),
            total_return=Decimal("7500"),
            return_percentage=12.5,
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        data = metrics.to_dict()
        
        assert isinstance(data, dict)
        assert data["total_value"] == 67500.0
        assert data["return_percentage"] == 12.5
        assert "timestamp" in data


class TestTrackingConfig:
    """Test TrackingConfig class."""
    
    def test_tracking_config_defaults(self):
        """Test default tracking configuration."""
        config = TrackingConfig()
        
        assert config.mode == TrackingMode.CONTINUOUS
        assert config.update_interval == 1.0
        assert config.enable_alerts is True
        assert config.enable_performance_tracking is True
    
    def test_tracking_config_custom(self):
        """Test custom tracking configuration."""
        config = TrackingConfig(
            mode=TrackingMode.INTERVAL,
            update_interval=0.5,
            enable_alerts=False
        )
        
        assert config.mode == TrackingMode.INTERVAL
        assert config.update_interval == 0.5
        assert config.enable_alerts is False


class TestRealTimePortfolioTracker:
    """Test RealTimePortfolioTracker class."""
    
    def test_tracker_creation(self):
        """Test creating real-time tracker."""
        config = TrackingConfig()
        tracker = RealTimePortfolioTracker(config)
        
        assert tracker.config == config
        assert tracker.current_holdings == {}
        assert tracker.current_prices == {}
        assert tracker._running is False
    
    def test_add_update_handler(self):
        """Test adding update handler."""
        tracker = RealTimePortfolioTracker()
        handler = Mock()
        
        tracker.add_update_handler(handler)
        
        assert handler in tracker.update_handlers
    
    def test_remove_update_handler(self):
        """Test removing update handler."""
        tracker = RealTimePortfolioTracker()
        handler = Mock()
        
        tracker.add_update_handler(handler)
        tracker.remove_update_handler(handler)
        
        assert handler not in tracker.update_handlers
    
    @pytest.mark.asyncio
    async def test_add_holding(self):
        """Test adding holding to tracker."""
        tracker = RealTimePortfolioTracker()
        
        holding = PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.0"),
            average_cost=Decimal("45000"),
            current_price=Decimal("50000")
        )
        
        await tracker.add_holding(holding)
        
        assert "BTC" in tracker.current_holdings
        assert tracker.current_holdings["BTC"] == holding
    
    @pytest.mark.asyncio
    async def test_remove_holding(self):
        """Test removing holding from tracker."""
        tracker = RealTimePortfolioTracker()
        
        holding = PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.0"),
            average_cost=Decimal("45000"),
            current_price=Decimal("50000")
        )
        
        await tracker.add_holding(holding)
        await tracker.remove_holding("BTC")
        
        assert "BTC" not in tracker.current_holdings


class TestAlert:
    """Test Alert class."""
    
    def test_alert_creation(self):
        """Test creating alert."""
        alert = Alert(
            alert_id="test_001",
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="This is a test alert",
            current_value=67500,
            threshold_value=60000
        )
        
        assert alert.alert_id == "test_001"
        assert alert.alert_type == AlertType.PORTFOLIO_VALUE
        assert alert.severity == AlertSeverity.INFO
        assert alert.current_value == 67500
    
    def test_alert_serialization(self):
        """Test alert to_dict method."""
        alert = Alert(
            alert_id="test_001",
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="This is a test alert"
        )
        
        data = alert.to_dict()
        
        assert isinstance(data, dict)
        assert data["alert_id"] == "test_001"
        assert data["alert_type"] == "portfolio_value"
        assert data["severity"] == "info"


class TestAlertRule:
    """Test AlertRule class."""
    
    def test_alert_rule_creation(self):
        """Test creating alert rule."""
        rule = AlertRule(
            rule_id="test_portfolio_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("100000"),
            severity=AlertSeverity.INFO
        )
        
        assert rule.rule_id == "test_portfolio_rule"
        assert rule.alert_type == AlertType.PORTFOLIO_VALUE
        assert rule.threshold_value == Decimal("100000")
        assert rule.enabled is True
    
    def test_alert_rule_percentage(self):
        """Test percentage-based alert rule."""
        rule = AlertRule(
            rule_id="test_percentage_rule",
            alert_type=AlertType.PERCENTAGE_CHANGE,
            percentage_threshold=10.0,
            severity=AlertSeverity.WARNING
        )
        
        assert rule.alert_type == AlertType.PERCENTAGE_CHANGE
        assert rule.percentage_threshold == 10.0
        assert rule.severity == AlertSeverity.WARNING


class TestEnhancedAlertManager:
    """Test EnhancedAlertManager class."""
    
    def test_alert_manager_creation(self):
        """Test creating alert manager."""
        manager = EnhancedAlertManager()
        
        assert manager.rules == {}
        assert manager.alert_history == []
        assert NotificationChannel.CONSOLE in manager.notification_handlers
    
    def test_add_alert_rule(self):
        """Test adding alert rule."""
        manager = EnhancedAlertManager()
        
        rule = AlertRule(
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("100000"),
            severity=AlertSeverity.INFO
        )
        
        manager.add_alert_rule(rule)
        
        assert "test_rule" in manager.rules
        assert manager.rules["test_rule"] == rule
    
    def test_remove_alert_rule(self):
        """Test removing alert rule."""
        manager = EnhancedAlertManager()
        
        rule = AlertRule(
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("100000"),
            severity=AlertSeverity.INFO
        )
        
        manager.add_alert_rule(rule)
        manager.remove_alert_rule("test_rule")
        
        assert "test_rule" not in manager.rules
    
    @pytest.mark.asyncio
    async def test_check_portfolio_alerts(self):
        """Test checking portfolio alerts."""
        manager = EnhancedAlertManager()
        
        # Add alert rule
        rule = AlertRule(
            rule_id="test_portfolio_alert",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("60000"),
            severity=AlertSeverity.INFO
        )
        manager.add_alert_rule(rule)
        
        # Create metrics that should trigger alert
        metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=Decimal("67500"),  # Above threshold
            total_cost=Decimal("60000"),
            total_return=Decimal("7500"),
            return_percentage=12.5,
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        await manager.check_portfolio_alerts(metrics)
        
        # Check that alert was triggered
        recent_alerts = manager.get_recent_alerts()
        assert len(recent_alerts) > 0
        assert recent_alerts[0].alert_type == AlertType.PORTFOLIO_VALUE


class TestConsoleNotificationHandler:
    """Test ConsoleNotificationHandler class."""
    
    def test_console_handler_creation(self):
        """Test creating console notification handler."""
        config = NotificationConfig(channel=NotificationChannel.CONSOLE)
        handler = ConsoleNotificationHandler(config)
        
        assert handler.config == config
        assert handler.enabled is True
    
    @pytest.mark.asyncio
    async def test_send_notification(self):
        """Test sending console notification."""
        config = NotificationConfig(channel=NotificationChannel.CONSOLE)
        handler = ConsoleNotificationHandler(config)
        
        alert = Alert(
            alert_id="test_001",
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="This is a test alert"
        )
        
        # Should not raise exception
        result = await handler.send_notification(alert)
        assert result is True


class TestStreamEvent:
    """Test StreamEvent class."""
    
    def test_stream_event_creation(self):
        """Test creating stream event."""
        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data={"total_value": 67500, "return_pct": 12.5},
            source="test"
        )
        
        assert event.event_type == EventType.PORTFOLIO_UPDATE
        assert event.data["total_value"] == 67500
        assert event.source == "test"
        assert event.event_id is not None
    
    def test_stream_event_serialization(self):
        """Test stream event serialization."""
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000},
            source="test"
        )
        
        # Test to_dict
        data = event.to_dict()
        assert isinstance(data, dict)
        assert data["event_type"] == "price_update"
        assert data["source"] == "test"
        
        # Test to_json
        json_str = event.to_json()
        assert isinstance(json_str, str)
        assert "price_update" in json_str
    
    def test_stream_event_from_dict(self):
        """Test creating stream event from dictionary."""
        data = {
            "event_type": "portfolio_update",
            "data": {"total_value": 67500},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test",
            "event_id": "test_123"
        }
        
        event = StreamEvent.from_dict(data)
        
        assert event.event_type == EventType.PORTFOLIO_UPDATE
        assert event.data["total_value"] == 67500
        assert event.source == "test"


class TestStreamEventBus:
    """Test StreamEventBus class."""
    
    @pytest.mark.asyncio
    async def test_event_bus_creation(self):
        """Test creating event bus."""
        event_bus = StreamEventBus()
        
        assert event_bus.subscribers == {}
        assert event_bus.running is False
    
    @pytest.mark.asyncio
    async def test_event_bus_start_stop(self):
        """Test starting and stopping event bus."""
        event_bus = StreamEventBus()
        
        await event_bus.start()
        assert event_bus.running is True
        
        await event_bus.stop()
        assert event_bus.running is False
    
    @pytest.mark.asyncio
    async def test_event_subscription(self):
        """Test event subscription."""
        event_bus = StreamEventBus()
        handler = AsyncMock()
        
        event_bus.subscribe("test_subscriber", handler)
        
        assert "test_subscriber" in event_bus.subscribers
    
    @pytest.mark.asyncio
    async def test_event_publishing(self):
        """Test event publishing."""
        event_bus = StreamEventBus()
        await event_bus.start()
        
        handler = AsyncMock()
        event_bus.subscribe("test_subscriber", handler)
        
        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data={"test": "data"},
            source="test"
        )
        
        await event_bus.publish(event)
        await asyncio.sleep(0.1)  # Allow event processing
        
        handler.assert_called_once_with(event)
        
        await event_bus.stop()


# Integration tests
class TestIntegration:
    """Integration tests for real-time monitoring."""
    
    @pytest.mark.asyncio
    async def test_tracker_alert_integration(self):
        """Test integration between tracker and alert system."""
        # Create tracker
        tracker = RealTimePortfolioTracker()
        
        # Create alert manager
        alert_manager = EnhancedAlertManager()
        
        # Add alert rule
        rule = AlertRule(
            rule_id="integration_test",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("50000"),
            severity=AlertSeverity.INFO
        )
        alert_manager.add_alert_rule(rule)
        
        # Create test metrics
        metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=Decimal("67500"),
            total_cost=Decimal("60000"),
            total_return=Decimal("7500"),
            return_percentage=12.5,
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        # Test alert checking
        await alert_manager.check_portfolio_alerts(metrics)
        
        alerts = alert_manager.get_recent_alerts()
        assert len(alerts) > 0
        
        # Verify alert content
        alert = alerts[0]
        assert alert.rule_id == "integration_test"
        assert alert.current_value == 67500.0

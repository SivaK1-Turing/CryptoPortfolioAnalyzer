"""Comprehensive real-time portfolio monitoring service."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json

from ..analytics.models import PortfolioHolding
from .realtime_tracker import RealTimePortfolioTracker, TrackingConfig, PortfolioMetrics, HoldingUpdate
from .alerts import EnhancedAlertManager, NotificationConfig, NotificationChannel, AlertRule, AlertType, AlertSeverity
from .events import StreamEvent, EventType, StreamEventBus
from .price_feeds import PriceFeedManager

logger = logging.getLogger(__name__)


class MonitoringStatus(Enum):
    """Monitoring service status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class MonitoringConfig:
    """Configuration for monitoring service."""
    tracking_config: TrackingConfig = field(default_factory=TrackingConfig)
    enable_alerts: bool = True
    enable_performance_tracking: bool = True
    enable_risk_monitoring: bool = True
    auto_start: bool = False
    health_check_interval: float = 30.0  # seconds
    max_connection_retries: int = 5
    notification_channels: List[NotificationConfig] = field(default_factory=list)


@dataclass
class MonitoringStats:
    """Monitoring service statistics."""
    start_time: datetime
    uptime_seconds: float
    total_price_updates: int = 0
    total_portfolio_updates: int = 0
    total_alerts_triggered: int = 0
    connection_errors: int = 0
    last_update: Optional[datetime] = None
    symbols_tracked: int = 0
    active_alert_rules: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "total_price_updates": self.total_price_updates,
            "total_portfolio_updates": self.total_portfolio_updates,
            "total_alerts_triggered": self.total_alerts_triggered,
            "connection_errors": self.connection_errors,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "symbols_tracked": self.symbols_tracked,
            "active_alert_rules": self.active_alert_rules
        }


class RealTimeMonitoringService:
    """Comprehensive real-time portfolio monitoring service."""
    
    def __init__(self, config: MonitoringConfig = None):
        """Initialize monitoring service.
        
        Args:
            config: Monitoring configuration
        """
        self.config = config or MonitoringConfig()
        
        # Core components
        self.tracker = RealTimePortfolioTracker(self.config.tracking_config)
        self.alert_manager = EnhancedAlertManager()
        self.event_bus = StreamEventBus()
        
        # State
        self.status = MonitoringStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.stats = MonitoringStats(start_time=datetime.now(timezone.utc), uptime_seconds=0)
        
        # Tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._stats_update_task: Optional[asyncio.Task] = None
        
        # Event handlers
        self.status_handlers: Set[Callable[[MonitoringStatus], None]] = set()
        self.metrics_handlers: Set[Callable[[PortfolioMetrics], None]] = set()
        self.alert_handlers: Set[Callable[[Any], None]] = set()
        
        # Setup internal handlers
        self._setup_internal_handlers()
        
        # Setup notification channels
        self._setup_notification_channels()
    
    def _setup_internal_handlers(self):
        """Setup internal event handlers."""
        # Portfolio update handler
        self.tracker.add_update_handler(self._handle_portfolio_update)
        
        # Holding update handler
        self.tracker.add_holding_handler(self._handle_holding_update)
        
        # Event bus handlers
        self.event_bus.subscribe(
            "monitoring_service",
            self._handle_stream_event,
            event_types={EventType.PRICE_UPDATE, EventType.ALERT_TRIGGERED}
        )
    
    def _setup_notification_channels(self):
        """Setup notification channels from config."""
        for notification_config in self.config.notification_channels:
            try:
                if notification_config.channel == NotificationChannel.EMAIL:
                    from .alerts import EmailNotificationHandler
                    handler = EmailNotificationHandler(notification_config)
                    self.alert_manager.add_notification_handler(handler)
                
                elif notification_config.channel == NotificationChannel.WEBHOOK:
                    from .alerts import WebhookNotificationHandler
                    handler = WebhookNotificationHandler(notification_config)
                    self.alert_manager.add_notification_handler(handler)
                
                elif notification_config.channel == NotificationChannel.SLACK:
                    from .alerts import SlackNotificationHandler
                    handler = SlackNotificationHandler(notification_config)
                    self.alert_manager.add_notification_handler(handler)
                
                logger.info(f"Setup {notification_config.channel.value} notification channel")
                
            except Exception as e:
                logger.error(f"Failed to setup {notification_config.channel.value} notification: {e}")
    
    async def start(self, holdings: List[PortfolioHolding]):
        """Start monitoring service.
        
        Args:
            holdings: Portfolio holdings to monitor
        """
        if self.status != MonitoringStatus.STOPPED:
            logger.warning(f"Cannot start monitoring service in {self.status.value} state")
            return
        
        logger.info("Starting real-time monitoring service")
        self.status = MonitoringStatus.STARTING
        self._notify_status_handlers()
        
        try:
            # Start core components
            await self.tracker.start(holdings)
            
            # Start background tasks
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._stats_update_task = asyncio.create_task(self._stats_update_loop())
            
            # Update state
            self.status = MonitoringStatus.RUNNING
            self.start_time = datetime.now(timezone.utc)
            self.stats.start_time = self.start_time
            self.stats.symbols_tracked = len(holdings)
            self.stats.active_alert_rules = len(self.alert_manager.get_alert_rules())
            
            logger.info(f"Monitoring service started for {len(holdings)} holdings")
            self._notify_status_handlers()
            
        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            self.status = MonitoringStatus.ERROR
            self._notify_status_handlers()
            raise
    
    async def stop(self):
        """Stop monitoring service."""
        if self.status == MonitoringStatus.STOPPED:
            return
        
        logger.info("Stopping real-time monitoring service")
        self.status = MonitoringStatus.STOPPING
        self._notify_status_handlers()
        
        try:
            # Stop background tasks
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            if self._stats_update_task:
                self._stats_update_task.cancel()
                try:
                    await self._stats_update_task
                except asyncio.CancelledError:
                    pass
            
            # Stop core components
            await self.tracker.stop()
            
            # Update state
            self.status = MonitoringStatus.STOPPED
            logger.info("Monitoring service stopped")
            self._notify_status_handlers()
            
        except Exception as e:
            logger.error(f"Error stopping monitoring service: {e}")
            self.status = MonitoringStatus.ERROR
            self._notify_status_handlers()
    
    def add_status_handler(self, handler: Callable[[MonitoringStatus], None]):
        """Add status change handler."""
        self.status_handlers.add(handler)
    
    def remove_status_handler(self, handler: Callable[[MonitoringStatus], None]):
        """Remove status change handler."""
        self.status_handlers.discard(handler)
    
    def add_metrics_handler(self, handler: Callable[[PortfolioMetrics], None]):
        """Add portfolio metrics handler."""
        self.metrics_handlers.add(handler)
    
    def remove_metrics_handler(self, handler: Callable[[PortfolioMetrics], None]):
        """Remove portfolio metrics handler."""
        self.metrics_handlers.discard(handler)
    
    def add_alert_handler(self, handler: Callable[[Any], None]):
        """Add alert handler."""
        self.alert_handlers.add(handler)
    
    def remove_alert_handler(self, handler: Callable[[Any], None]):
        """Remove alert handler."""
        self.alert_handlers.discard(handler)
    
    def add_alert_rule(self, rule: AlertRule):
        """Add alert rule."""
        self.alert_manager.add_alert_rule(rule)
        self.stats.active_alert_rules = len(self.alert_manager.get_alert_rules())
    
    def remove_alert_rule(self, rule_id: str):
        """Remove alert rule."""
        self.alert_manager.remove_alert_rule(rule_id)
        self.stats.active_alert_rules = len(self.alert_manager.get_alert_rules())
    
    async def add_holding(self, holding: PortfolioHolding):
        """Add new holding to monitor."""
        await self.tracker.add_holding(holding)
        self.stats.symbols_tracked = len(self.tracker.current_holdings)
    
    async def remove_holding(self, symbol: str):
        """Remove holding from monitoring."""
        await self.tracker.remove_holding(symbol)
        self.stats.symbols_tracked = len(self.tracker.current_holdings)
    
    async def update_holding_quantity(self, symbol: str, new_quantity: Decimal):
        """Update holding quantity."""
        await self.tracker.update_holding_quantity(symbol, new_quantity)
    
    def get_status(self) -> MonitoringStatus:
        """Get current status."""
        return self.status
    
    def get_stats(self) -> MonitoringStats:
        """Get monitoring statistics."""
        if self.start_time:
            self.stats.uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return self.stats
    
    def get_current_metrics(self) -> Optional[PortfolioMetrics]:
        """Get current portfolio metrics."""
        return self.tracker.get_current_metrics()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return self.tracker.get_performance_summary()
    
    def get_recent_alerts(self, hours: int = 24) -> List[Any]:
        """Get recent alerts."""
        return self.alert_manager.get_recent_alerts(hours)
    
    async def force_update(self):
        """Force immediate portfolio update."""
        await self.tracker.force_update()
    
    async def _handle_portfolio_update(self, metrics: PortfolioMetrics):
        """Handle portfolio update."""
        self.stats.total_portfolio_updates += 1
        self.stats.last_update = metrics.timestamp
        
        # Check alerts
        if self.config.enable_alerts:
            await self.alert_manager.check_portfolio_alerts(metrics)
        
        # Notify handlers
        for handler in self.metrics_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(metrics))
                else:
                    handler(metrics)
            except Exception as e:
                logger.error(f"Error in metrics handler: {e}")
        
        # Broadcast event
        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data=metrics.to_dict(),
            source="monitoring_service"
        )
        await self.event_bus.publish(event)
    
    async def _handle_holding_update(self, symbol: str, holding_update: HoldingUpdate):
        """Handle holding update."""
        # Check alerts
        if self.config.enable_alerts:
            await self.alert_manager.check_holding_alerts(symbol, holding_update)
    
    async def _handle_stream_event(self, event: StreamEvent):
        """Handle stream events."""
        if event.event_type == EventType.PRICE_UPDATE:
            self.stats.total_price_updates += 1
        elif event.event_type == EventType.ALERT_TRIGGERED:
            self.stats.total_alerts_triggered += 1
            
            # Notify alert handlers
            for handler in self.alert_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(event.data))
                    else:
                        handler(event.data)
                except Exception as e:
                    logger.error(f"Error in alert handler: {e}")
    
    async def _health_check_loop(self):
        """Health check loop."""
        while self.status == MonitoringStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                # Check tracker health
                if not self.tracker._running:
                    logger.warning("Portfolio tracker is not running")
                    self.stats.connection_errors += 1
                
                # Check if we're receiving updates
                if self.stats.last_update:
                    time_since_update = (datetime.now(timezone.utc) - self.stats.last_update).total_seconds()
                    if time_since_update > 300:  # 5 minutes
                        logger.warning(f"No updates received for {time_since_update:.0f} seconds")
                
                # Broadcast health status
                health_data = {
                    "status": self.status.value,
                    "uptime": self.get_stats().uptime_seconds,
                    "last_update": self.stats.last_update.isoformat() if self.stats.last_update else None
                }
                
                event = StreamEvent(
                    event_type=EventType.SYSTEM_STATUS,
                    data=health_data,
                    source="monitoring_service"
                )
                await self.event_bus.publish(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                self.stats.connection_errors += 1
    
    async def _stats_update_loop(self):
        """Statistics update loop."""
        while self.status == MonitoringStatus.RUNNING:
            try:
                await asyncio.sleep(60)  # Update stats every minute
                
                # Update uptime
                if self.start_time:
                    self.stats.uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating stats: {e}")
    
    def _notify_status_handlers(self):
        """Notify status change handlers."""
        for handler in self.status_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(self.status))
                else:
                    handler(self.status)
            except Exception as e:
                logger.error(f"Error in status handler: {e}")


# Convenience functions for quick setup
def create_basic_monitoring_service(holdings: List[PortfolioHolding]) -> RealTimeMonitoringService:
    """Create a basic monitoring service with default configuration."""
    config = MonitoringConfig(
        enable_alerts=True,
        enable_performance_tracking=True,
        auto_start=False
    )
    
    service = RealTimeMonitoringService(config)
    
    # Add basic alert rules
    service.add_alert_rule(AlertRule(
        rule_id="portfolio_value_100k",
        alert_type=AlertType.PORTFOLIO_VALUE,
        threshold_value=Decimal("100000"),
        severity=AlertSeverity.INFO
    ))
    
    service.add_alert_rule(AlertRule(
        rule_id="portfolio_change_10pct",
        alert_type=AlertType.PERCENTAGE_CHANGE,
        percentage_threshold=10.0,
        severity=AlertSeverity.WARNING
    ))
    
    return service


def create_advanced_monitoring_service(
    holdings: List[PortfolioHolding],
    notification_configs: List[NotificationConfig] = None
) -> RealTimeMonitoringService:
    """Create an advanced monitoring service with custom notifications."""
    tracking_config = TrackingConfig(
        update_interval=0.5,  # 500ms updates
        enable_performance_tracking=True,
        enable_risk_metrics=True,
        history_retention_hours=48
    )
    
    config = MonitoringConfig(
        tracking_config=tracking_config,
        enable_alerts=True,
        enable_performance_tracking=True,
        enable_risk_monitoring=True,
        notification_channels=notification_configs or []
    )
    
    return RealTimeMonitoringService(config)

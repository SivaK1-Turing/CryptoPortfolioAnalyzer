"""Enhanced alert system with multiple notification channels."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod

from .portfolio_monitor import AlertRule, AlertType, AlertSeverity
from .events import StreamEvent, EventType, StreamEventBus
from .realtime_tracker import PortfolioMetrics, HoldingUpdate

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    FILE = "file"
    WEBSOCKET = "websocket"
    SLACK = "slack"
    DISCORD = "discord"


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Email specific
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_email: Optional[str] = None
    to_emails: List[str] = field(default_factory=list)
    
    # Webhook specific
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = field(default_factory=dict)
    
    # File specific
    log_file: Optional[str] = None
    
    # Slack/Discord specific
    webhook_token: Optional[str] = None


@dataclass
class Alert:
    """Alert instance."""
    alert_id: str
    rule_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    symbol: Optional[str] = None
    current_value: Optional[Union[Decimal, float]] = None
    threshold_value: Optional[Union[Decimal, float]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "symbol": self.symbol,
            "current_value": float(self.current_value) if self.current_value else None,
            "threshold_value": float(self.threshold_value) if self.threshold_value else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class BaseNotificationHandler(ABC):
    """Base class for notification handlers."""
    
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.enabled = config.enabled
    
    @abstractmethod
    async def send_notification(self, alert: Alert) -> bool:
        """Send notification for alert.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    def format_alert_message(self, alert: Alert) -> str:
        """Format alert message for display."""
        lines = [
            f"🚨 {alert.title}",
            f"Severity: {alert.severity.value.upper()}",
            f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            alert.message
        ]
        
        if alert.symbol:
            lines.insert(2, f"Symbol: {alert.symbol}")
        
        if alert.current_value is not None:
            lines.append(f"Current Value: {alert.current_value}")
        
        if alert.threshold_value is not None:
            lines.append(f"Threshold: {alert.threshold_value}")
        
        return "\n".join(lines)


class ConsoleNotificationHandler(BaseNotificationHandler):
    """Console notification handler."""
    
    async def send_notification(self, alert: Alert) -> bool:
        """Send console notification."""
        try:
            severity_colors = {
                AlertSeverity.INFO: "\033[94m",      # Blue
                AlertSeverity.WARNING: "\033[93m",   # Yellow
                AlertSeverity.CRITICAL: "\033[91m"   # Red
            }
            reset_color = "\033[0m"
            
            color = severity_colors.get(alert.severity, "")
            message = self.format_alert_message(alert)
            
            print(f"{color}{message}{reset_color}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending console notification: {e}")
            return False


class EmailNotificationHandler(BaseNotificationHandler):
    """Email notification handler."""
    
    async def send_notification(self, alert: Alert) -> bool:
        """Send email notification."""
        try:
            if not all([self.config.smtp_server, self.config.from_email, self.config.to_emails]):
                logger.error("Email configuration incomplete")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.from_email
            msg['To'] = ", ".join(self.config.to_emails)
            msg['Subject'] = f"Portfolio Alert: {alert.title}"
            
            # Create HTML body
            html_body = self._create_html_alert(alert)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port or 587) as server:
                if self.config.username and self.config.password:
                    server.starttls()
                    server.login(self.config.username, self.config.password)
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent for {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _create_html_alert(self, alert: Alert) -> str:
        """Create HTML formatted alert."""
        severity_colors = {
            AlertSeverity.INFO: "#17a2b8",
            AlertSeverity.WARNING: "#ffc107", 
            AlertSeverity.CRITICAL: "#dc3545"
        }
        
        color = severity_colors.get(alert.severity, "#6c757d")
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="border-left: 4px solid {color}; padding: 20px; background-color: #f8f9fa;">
                <h2 style="color: {color}; margin-top: 0;">🚨 {alert.title}</h2>
                <p><strong>Severity:</strong> <span style="color: {color};">{alert.severity.value.upper()}</span></p>
                <p><strong>Time:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                {f'<p><strong>Symbol:</strong> {alert.symbol}</p>' if alert.symbol else ''}
                <p><strong>Message:</strong></p>
                <p style="background-color: white; padding: 15px; border-radius: 5px;">{alert.message}</p>
                {f'<p><strong>Current Value:</strong> {alert.current_value}</p>' if alert.current_value is not None else ''}
                {f'<p><strong>Threshold:</strong> {alert.threshold_value}</p>' if alert.threshold_value is not None else ''}
            </div>
            <p style="color: #6c757d; font-size: 12px; margin-top: 20px;">
                This alert was generated by the Crypto Portfolio Analyzer real-time monitoring system.
            </p>
        </body>
        </html>
        """
        return html


class WebhookNotificationHandler(BaseNotificationHandler):
    """Webhook notification handler."""
    
    async def send_notification(self, alert: Alert) -> bool:
        """Send webhook notification."""
        try:
            import aiohttp
            
            if not self.config.webhook_url:
                logger.error("Webhook URL not configured")
                return False
            
            payload = {
                "alert": alert.to_dict(),
                "formatted_message": self.format_alert_message(alert)
            }
            
            headers = {"Content-Type": "application/json"}
            headers.update(self.config.webhook_headers)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook alert sent for {alert.alert_id}")
                        return True
                    else:
                        logger.error(f"Webhook failed with status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False


class FileNotificationHandler(BaseNotificationHandler):
    """File notification handler."""
    
    async def send_notification(self, alert: Alert) -> bool:
        """Send file notification."""
        try:
            log_file = self.config.log_file or "portfolio_alerts.log"
            
            message = self.format_alert_message(alert)
            log_entry = f"[{alert.timestamp.isoformat()}] {message}\n{'-'*50}\n"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing alert to file: {e}")
            return False


class SlackNotificationHandler(BaseNotificationHandler):
    """Slack notification handler."""
    
    async def send_notification(self, alert: Alert) -> bool:
        """Send Slack notification."""
        try:
            import aiohttp
            
            if not self.config.webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            # Create Slack message format
            severity_colors = {
                AlertSeverity.INFO: "#36a64f",      # Green
                AlertSeverity.WARNING: "#ff9500",   # Orange
                AlertSeverity.CRITICAL: "#ff0000"   # Red
            }
            
            color = severity_colors.get(alert.severity, "#36a64f")
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            }
                        ],
                        "footer": "Crypto Portfolio Analyzer",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            if alert.symbol:
                payload["attachments"][0]["fields"].insert(0, {
                    "title": "Symbol",
                    "value": alert.symbol,
                    "short": True
                })
            
            if alert.current_value is not None:
                payload["attachments"][0]["fields"].append({
                    "title": "Current Value",
                    "value": str(alert.current_value),
                    "short": True
                })
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack alert sent for {alert.alert_id}")
                        return True
                    else:
                        logger.error(f"Slack webhook failed with status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False


class EnhancedAlertManager:
    """Enhanced alert management system."""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.notification_handlers: Dict[NotificationChannel, BaseNotificationHandler] = {}
        self.alert_history: List[Alert] = []
        self.cooldown_tracker: Dict[str, datetime] = {}
        self.event_bus = StreamEventBus()
        
        # Default handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default notification handlers."""
        # Console handler (always available)
        console_config = NotificationConfig(channel=NotificationChannel.CONSOLE)
        self.notification_handlers[NotificationChannel.CONSOLE] = ConsoleNotificationHandler(console_config)
        
        # File handler (always available)
        file_config = NotificationConfig(channel=NotificationChannel.FILE, log_file="portfolio_alerts.log")
        self.notification_handlers[NotificationChannel.FILE] = FileNotificationHandler(file_config)
    
    def add_notification_handler(self, handler: BaseNotificationHandler):
        """Add notification handler."""
        self.notification_handlers[handler.config.channel] = handler
        logger.info(f"Added {handler.config.channel.value} notification handler")
    
    def remove_notification_handler(self, channel: NotificationChannel):
        """Remove notification handler."""
        if channel in self.notification_handlers:
            del self.notification_handlers[channel]
            logger.info(f"Removed {channel.value} notification handler")
    
    def add_alert_rule(self, rule: AlertRule):
        """Add alert rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.rule_id}")
    
    def remove_alert_rule(self, rule_id: str):
        """Remove alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")
    
    def get_alert_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        return list(self.rules.values())
    
    async def check_portfolio_alerts(self, metrics: PortfolioMetrics):
        """Check portfolio-level alerts."""
        for rule in self.rules.values():
            if not rule.enabled or rule.symbol is not None:
                continue
            
            if await self._is_in_cooldown(rule.rule_id):
                continue
            
            alert = await self._evaluate_portfolio_rule(rule, metrics)
            if alert:
                await self._trigger_alert(alert)
    
    async def check_holding_alerts(self, symbol: str, holding_update: HoldingUpdate):
        """Check holding-specific alerts."""
        for rule in self.rules.values():
            if not rule.enabled or rule.symbol != symbol:
                continue
            
            if await self._is_in_cooldown(f"{rule.rule_id}_{symbol}"):
                continue
            
            alert = await self._evaluate_holding_rule(rule, symbol, holding_update)
            if alert:
                await self._trigger_alert(alert)
    
    async def _evaluate_portfolio_rule(self, rule: AlertRule, metrics: PortfolioMetrics) -> Optional[Alert]:
        """Evaluate portfolio-level alert rule."""
        if rule.alert_type == AlertType.PORTFOLIO_VALUE:
            if rule.threshold_value and metrics.total_value >= rule.threshold_value:
                return Alert(
                    alert_id=f"{rule.rule_id}_{int(metrics.timestamp.timestamp())}",
                    rule_id=rule.rule_id,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title="Portfolio Value Threshold Reached",
                    message=f"Portfolio value ${metrics.total_value:,.2f} has reached the threshold of ${rule.threshold_value:,.2f}",
                    current_value=float(metrics.total_value),
                    threshold_value=float(rule.threshold_value)
                )
        
        elif rule.alert_type == AlertType.PERCENTAGE_CHANGE:
            if rule.percentage_threshold and abs(metrics.return_percentage) >= rule.percentage_threshold:
                direction = "gained" if metrics.return_percentage > 0 else "lost"
                return Alert(
                    alert_id=f"{rule.rule_id}_{int(metrics.timestamp.timestamp())}",
                    rule_id=rule.rule_id,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title=f"Portfolio {direction.title()} {abs(metrics.return_percentage):.2f}%",
                    message=f"Portfolio has {direction} {abs(metrics.return_percentage):.2f}% (${metrics.total_return:,.2f})",
                    current_value=metrics.return_percentage,
                    threshold_value=rule.percentage_threshold
                )
        
        return None
    
    async def _evaluate_holding_rule(self, rule: AlertRule, symbol: str, holding_update: HoldingUpdate) -> Optional[Alert]:
        """Evaluate holding-specific alert rule."""
        if rule.alert_type == AlertType.PRICE_THRESHOLD:
            if rule.threshold_value and holding_update.current_price >= rule.threshold_value:
                return Alert(
                    alert_id=f"{rule.rule_id}_{symbol}_{int(holding_update.last_updated.timestamp())}",
                    rule_id=rule.rule_id,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title=f"{symbol} Price Alert",
                    message=f"{symbol} price ${holding_update.current_price:,.2f} has reached the threshold of ${rule.threshold_value:,.2f}",
                    symbol=symbol,
                    current_value=float(holding_update.current_price),
                    threshold_value=float(rule.threshold_value)
                )
        
        elif rule.alert_type == AlertType.STOP_LOSS:
            if rule.threshold_value and holding_update.current_price <= rule.threshold_value:
                return Alert(
                    alert_id=f"{rule.rule_id}_{symbol}_{int(holding_update.last_updated.timestamp())}",
                    rule_id=rule.rule_id,
                    alert_type=rule.alert_type,
                    severity=AlertSeverity.CRITICAL,
                    title=f"{symbol} Stop Loss Triggered",
                    message=f"{symbol} price ${holding_update.current_price:,.2f} has fallen below stop loss of ${rule.threshold_value:,.2f}",
                    symbol=symbol,
                    current_value=float(holding_update.current_price),
                    threshold_value=float(rule.threshold_value)
                )
        
        return None
    
    async def _trigger_alert(self, alert: Alert):
        """Trigger alert and send notifications."""
        logger.info(f"Triggering alert: {alert.alert_id}")
        
        # Store alert
        self.alert_history.append(alert)
        
        # Update cooldown
        cooldown_key = f"{alert.rule_id}_{alert.symbol}" if alert.symbol else alert.rule_id
        self.cooldown_tracker[cooldown_key] = alert.timestamp
        
        # Send notifications
        for handler in self.notification_handlers.values():
            if handler.enabled:
                try:
                    await handler.send_notification(alert)
                except Exception as e:
                    logger.error(f"Error sending notification via {handler.config.channel.value}: {e}")
        
        # Broadcast event
        event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data=alert.to_dict(),
            source="alert_manager"
        )
        await self.event_bus.publish(event)
    
    async def _is_in_cooldown(self, key: str) -> bool:
        """Check if alert is in cooldown period."""
        if key not in self.cooldown_tracker:
            return False
        
        rule_id = key.split('_')[0]
        rule = self.rules.get(rule_id)
        if not rule:
            return False
        
        last_alert = self.cooldown_tracker[key]
        cooldown_period = timedelta(minutes=rule.cooldown_minutes)
        
        return datetime.now(timezone.utc) - last_alert < cooldown_period
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get recent alerts."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff]

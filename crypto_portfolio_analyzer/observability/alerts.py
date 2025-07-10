"""Alert management and notification system."""

import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: str
    severity: AlertSeverity
    channels: List[AlertChannel]
    description: str
    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes
    last_triggered: Optional[datetime] = None
    
    def should_trigger(self) -> bool:
        """Check if alert should trigger based on cooldown."""
        if not self.enabled:
            return False
        
        if self.last_triggered is None:
            return True
        
        time_since_last = datetime.now(timezone.utc) - self.last_triggered
        return time_since_last.total_seconds() >= self.cooldown_seconds


@dataclass
class Alert:
    """Alert instance."""
    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class AlertManager:
    """Alert management system."""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.handlers: Dict[AlertChannel, Callable] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        
        # Setup default handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default alert handlers."""
        def log_handler(alert: Alert):
            print(f"ALERT [{alert.severity.value.upper()}] {alert.rule_name}: {alert.message}")
        
        self.handlers[AlertChannel.LOG] = log_handler
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule."""
        self.rules[rule.name] = rule
    
    def remove_rule(self, rule_name: str):
        """Remove alert rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
    
    def add_handler(self, channel: AlertChannel, handler: Callable):
        """Add alert handler for channel."""
        self.handlers[channel] = handler
    
    def trigger_alert(self, rule_name: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Trigger an alert."""
        if rule_name not in self.rules:
            return
        
        rule = self.rules[rule_name]
        
        if not rule.should_trigger():
            return
        
        # Create alert
        alert = Alert(
            rule_name=rule_name,
            severity=rule.severity,
            message=message,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        # Update rule last triggered time
        rule.last_triggered = alert.timestamp
        
        # Send to configured channels
        for channel in rule.channels:
            if channel in self.handlers:
                try:
                    self.handlers[channel](alert)
                except Exception as e:
                    print(f"Error sending alert to {channel.value}: {e}")
        
        # Store in history
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get recent alerts."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        
        return [
            alert for alert in self.alert_history
            if alert.timestamp.timestamp() >= cutoff_time
        ]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary."""
        recent_alerts = self.get_recent_alerts(24)
        
        severity_counts = {severity.value: 0 for severity in AlertSeverity}
        for alert in recent_alerts:
            severity_counts[alert.severity.value] += 1
        
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "recent_alerts_24h": len(recent_alerts),
            "severity_breakdown": severity_counts,
            "last_alert": recent_alerts[-1].to_dict() if recent_alerts else None
        }


# Global alert manager
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def send_alert(rule_name: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Send an alert using the global alert manager."""
    get_alert_manager().trigger_alert(rule_name, message, metadata)


def setup_alerting():
    """Setup default alerting rules."""
    alert_manager = get_alert_manager()
    
    # Default alert rules
    default_rules = [
        AlertRule(
            name="high_cpu_usage",
            condition="cpu_usage > 90",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            description="High CPU usage detected"
        ),
        AlertRule(
            name="high_memory_usage",
            condition="memory_usage > 90",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            description="High memory usage detected"
        ),
        AlertRule(
            name="application_error",
            condition="error_rate > 0.1",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.LOG],
            description="High application error rate"
        ),
        AlertRule(
            name="health_check_failure",
            condition="health_status != healthy",
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG],
            description="Health check failure detected"
        )
    ]
    
    for rule in default_rules:
        alert_manager.add_rule(rule)

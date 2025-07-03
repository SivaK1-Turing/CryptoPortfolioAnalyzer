"""Real-time portfolio monitoring system with alerts and notifications."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json

from ..analytics.portfolio import PortfolioAnalyzer
from ..analytics.models import PortfolioHolding
from .price_feeds import PriceUpdate, PriceFeedManager

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of portfolio alerts."""
    PRICE_THRESHOLD = "price_threshold"
    PORTFOLIO_VALUE = "portfolio_value"
    PERCENTAGE_CHANGE = "percentage_change"
    VOLUME_SPIKE = "volume_spike"
    REBALANCE_NEEDED = "rebalance_needed"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """Configuration for portfolio alerts."""
    
    rule_id: str
    alert_type: AlertType
    symbol: Optional[str] = None  # None for portfolio-wide alerts
    threshold_value: Optional[Decimal] = None
    percentage_threshold: Optional[float] = None
    enabled: bool = True
    severity: AlertSeverity = AlertSeverity.INFO
    cooldown_minutes: int = 5  # Minimum time between same alerts
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "alert_type": self.alert_type.value,
            "symbol": self.symbol,
            "threshold_value": float(self.threshold_value) if self.threshold_value else None,
            "percentage_threshold": self.percentage_threshold,
            "enabled": self.enabled,
            "severity": self.severity.value,
            "cooldown_minutes": self.cooldown_minutes,
            "metadata": self.metadata
        }


@dataclass
class Alert:
    """Portfolio alert notification."""
    
    alert_id: str
    rule_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    symbol: Optional[str] = None
    current_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
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


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio state at a point in time."""
    
    total_value: Decimal
    holdings: Dict[str, Dict[str, Any]]  # symbol -> holding data
    performance_24h: float
    performance_7d: float
    performance_30d: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_value": float(self.total_value),
            "holdings": self.holdings,
            "performance_24h": self.performance_24h,
            "performance_7d": self.performance_7d,
            "performance_30d": self.performance_30d,
            "timestamp": self.timestamp.isoformat()
        }


class PortfolioMonitor:
    """Real-time portfolio monitoring with alerts and notifications."""
    
    def __init__(self, portfolio_analyzer: PortfolioAnalyzer):
        self.portfolio_analyzer = portfolio_analyzer
        self.alert_rules: Dict[str, AlertRule] = {}
        self.alert_handlers: Set[Callable[[Alert], None]] = set()
        self.portfolio_handlers: Set[Callable[[PortfolioSnapshot], None]] = set()
        self.price_feed_manager: Optional[PriceFeedManager] = None
        
        self._running = False
        self._current_prices: Dict[str, PriceUpdate] = {}
        self._last_portfolio_snapshot: Optional[PortfolioSnapshot] = None
        self._alert_cooldowns: Dict[str, datetime] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
    def set_price_feed_manager(self, price_feed_manager: PriceFeedManager):
        """Set the price feed manager for real-time updates."""
        self.price_feed_manager = price_feed_manager
        self.price_feed_manager.add_handler(self._handle_price_update)
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.rule_id} ({rule.alert_type.value})")
    
    def remove_alert_rule(self, rule_id: str):
        """Remove an alert rule."""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add alert notification handler."""
        self.alert_handlers.add(handler)
    
    def remove_alert_handler(self, handler: Callable[[Alert], None]):
        """Remove alert notification handler."""
        self.alert_handlers.discard(handler)
    
    def add_portfolio_handler(self, handler: Callable[[PortfolioSnapshot], None]):
        """Add portfolio update handler."""
        self.portfolio_handlers.add(handler)
    
    def remove_portfolio_handler(self, handler: Callable[[PortfolioSnapshot], None]):
        """Remove portfolio update handler."""
        self.portfolio_handlers.discard(handler)
    
    async def start(self):
        """Start portfolio monitoring."""
        if self._running:
            return
            
        self._running = True
        
        # Start periodic monitoring
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Generate initial portfolio snapshot
        await self._update_portfolio_snapshot()
        
        logger.info("Portfolio monitor started")
    
    async def stop(self):
        """Stop portfolio monitoring."""
        if not self._running:
            return
            
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            
        logger.info("Portfolio monitor stopped")
    
    async def _handle_price_update(self, price_update: PriceUpdate):
        """Handle real-time price update."""
        self._current_prices[price_update.symbol] = price_update
        
        # Check price-based alert rules
        await self._check_price_alerts(price_update)
        
        # Update portfolio snapshot if this symbol is in portfolio
        holdings = await self.portfolio_analyzer.get_holdings()
        if any(holding.symbol == price_update.symbol for holding in holdings):
            await self._update_portfolio_snapshot()
    
    async def _update_portfolio_snapshot(self):
        """Update current portfolio snapshot."""
        try:
            holdings = await self.portfolio_analyzer.get_holdings()
            total_value = Decimal("0")
            holdings_data = {}
            
            for holding in holdings:
                current_price = self._current_prices.get(holding.symbol)
                if current_price:
                    holding_value = holding.quantity * current_price.price
                    total_value += holding_value
                    
                    holdings_data[holding.symbol] = {
                        "quantity": float(holding.quantity),
                        "current_price": float(current_price.price),
                        "value": float(holding_value),
                        "cost_basis": float(holding.cost_basis),
                        "unrealized_pnl": float(holding_value - holding.cost_basis),
                        "last_updated": current_price.timestamp.isoformat()
                    }
            
            # Calculate performance (simplified - would need historical data for accurate calculation)
            performance_24h = 0.0
            performance_7d = 0.0
            performance_30d = 0.0
            
            if self._last_portfolio_snapshot:
                value_change = total_value - self._last_portfolio_snapshot.total_value
                performance_24h = float(value_change / self._last_portfolio_snapshot.total_value * 100)
            
            snapshot = PortfolioSnapshot(
                total_value=total_value,
                holdings=holdings_data,
                performance_24h=performance_24h,
                performance_7d=performance_7d,
                performance_30d=performance_30d
            )
            
            # Check portfolio-based alerts
            await self._check_portfolio_alerts(snapshot)
            
            # Notify handlers
            for handler in self.portfolio_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(snapshot))
                    else:
                        handler(snapshot)
                except Exception as e:
                    logger.error(f"Error in portfolio handler: {e}")
            
            self._last_portfolio_snapshot = snapshot
            
        except Exception as e:
            logger.error(f"Error updating portfolio snapshot: {e}")
    
    async def _check_price_alerts(self, price_update: PriceUpdate):
        """Check price-based alert rules."""
        for rule in self.alert_rules.values():
            if not rule.enabled or rule.symbol != price_update.symbol:
                continue
                
            # Check cooldown
            if self._is_in_cooldown(rule.rule_id):
                continue
            
            alert = None
            
            if rule.alert_type == AlertType.PRICE_THRESHOLD and rule.threshold_value:
                if price_update.price >= rule.threshold_value:
                    alert = Alert(
                        alert_id=f"{rule.rule_id}_{int(price_update.timestamp.timestamp())}",
                        rule_id=rule.rule_id,
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title=f"Price Alert: {price_update.symbol}",
                        message=f"{price_update.symbol} price ${price_update.price} reached threshold ${rule.threshold_value}",
                        symbol=price_update.symbol,
                        current_value=price_update.price,
                        threshold_value=rule.threshold_value
                    )
            
            elif rule.alert_type == AlertType.PERCENTAGE_CHANGE and rule.percentage_threshold:
                if price_update.change_percent_24h and abs(price_update.change_percent_24h) >= rule.percentage_threshold:
                    alert = Alert(
                        alert_id=f"{rule.rule_id}_{int(price_update.timestamp.timestamp())}",
                        rule_id=rule.rule_id,
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title=f"Price Change Alert: {price_update.symbol}",
                        message=f"{price_update.symbol} changed {price_update.change_percent_24h:.2f}% in 24h",
                        symbol=price_update.symbol,
                        current_value=Decimal(str(price_update.change_percent_24h)),
                        threshold_value=Decimal(str(rule.percentage_threshold))
                    )
            
            if alert:
                await self._send_alert(alert)
                self._alert_cooldowns[rule.rule_id] = datetime.now(timezone.utc)
    
    async def _check_portfolio_alerts(self, snapshot: PortfolioSnapshot):
        """Check portfolio-based alert rules."""
        for rule in self.alert_rules.values():
            if not rule.enabled or rule.symbol is not None:  # Portfolio-wide rules only
                continue
                
            # Check cooldown
            if self._is_in_cooldown(rule.rule_id):
                continue
            
            alert = None
            
            if rule.alert_type == AlertType.PORTFOLIO_VALUE and rule.threshold_value:
                if snapshot.total_value >= rule.threshold_value:
                    alert = Alert(
                        alert_id=f"{rule.rule_id}_{int(snapshot.timestamp.timestamp())}",
                        rule_id=rule.rule_id,
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title="Portfolio Value Alert",
                        message=f"Portfolio value ${snapshot.total_value} reached threshold ${rule.threshold_value}",
                        current_value=snapshot.total_value,
                        threshold_value=rule.threshold_value
                    )
            
            elif rule.alert_type == AlertType.REBALANCE_NEEDED:
                # Check if portfolio needs rebalancing (simplified logic)
                if await self._needs_rebalancing(snapshot):
                    alert = Alert(
                        alert_id=f"{rule.rule_id}_{int(snapshot.timestamp.timestamp())}",
                        rule_id=rule.rule_id,
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title="Rebalancing Alert",
                        message="Portfolio allocation has drifted from target - consider rebalancing",
                        metadata={"portfolio_value": float(snapshot.total_value)}
                    )
            
            if alert:
                await self._send_alert(alert)
                self._alert_cooldowns[rule.rule_id] = datetime.now(timezone.utc)
    
    async def _needs_rebalancing(self, snapshot: PortfolioSnapshot) -> bool:
        """Check if portfolio needs rebalancing (simplified logic)."""
        # This is a simplified implementation
        # In practice, you'd compare current allocation to target allocation
        total_value = snapshot.total_value
        if total_value == 0:
            return False
            
        # Check if any holding is more than 50% of portfolio
        for holding_data in snapshot.holdings.values():
            allocation_percent = holding_data["value"] / float(total_value) * 100
            if allocation_percent > 50:
                return True
                
        return False
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if alert rule is in cooldown period."""
        if rule_id not in self._alert_cooldowns:
            return False
            
        rule = self.alert_rules.get(rule_id)
        if not rule:
            return False
            
        last_alert_time = self._alert_cooldowns[rule_id]
        cooldown_end = last_alert_time + timedelta(minutes=rule.cooldown_minutes)
        
        return datetime.now(timezone.utc) < cooldown_end
    
    async def _send_alert(self, alert: Alert):
        """Send alert to all handlers."""
        logger.info(f"Alert triggered: {alert.title} - {alert.message}")
        
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(alert))
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    async def _monitor_loop(self):
        """Periodic monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Clean up old cooldowns
                current_time = datetime.now(timezone.utc)
                expired_cooldowns = [
                    rule_id for rule_id, last_time in self._alert_cooldowns.items()
                    if (current_time - last_time).total_seconds() > 3600  # 1 hour
                ]
                
                for rule_id in expired_cooldowns:
                    del self._alert_cooldowns[rule_id]
                
                # Update portfolio snapshot if we have price data
                if self._current_prices:
                    await self._update_portfolio_snapshot()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
    
    def get_current_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Get the current portfolio snapshot."""
        return self._last_portfolio_snapshot
    
    def get_alert_rules(self) -> Dict[str, AlertRule]:
        """Get all alert rules."""
        return self.alert_rules.copy()
    
    def get_current_prices(self) -> Dict[str, PriceUpdate]:
        """Get current price data."""
        return self._current_prices.copy()

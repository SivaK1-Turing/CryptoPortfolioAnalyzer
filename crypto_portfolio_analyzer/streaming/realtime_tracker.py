"""Enhanced real-time portfolio tracking with advanced monitoring capabilities."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from collections import defaultdict, deque
import statistics

from ..analytics.portfolio import PortfolioAnalyzer
from ..analytics.models import PortfolioSnapshot, PortfolioHolding
from .price_feeds import PriceUpdate, PriceFeedManager
from .events import StreamEvent, EventType, StreamEventBus
from .portfolio_monitor import AlertRule, AlertType, AlertSeverity

logger = logging.getLogger(__name__)


class TrackingMode(Enum):
    """Portfolio tracking modes."""
    CONTINUOUS = "continuous"  # Real-time updates
    INTERVAL = "interval"      # Periodic updates
    ON_DEMAND = "on_demand"    # Manual updates only


class PerformanceMetric(Enum):
    """Performance metrics to track."""
    TOTAL_VALUE = "total_value"
    TOTAL_RETURN = "total_return"
    RETURN_PERCENTAGE = "return_percentage"
    DAILY_PNL = "daily_pnl"
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"


@dataclass
class TrackingConfig:
    """Configuration for real-time tracking."""
    mode: TrackingMode = TrackingMode.CONTINUOUS
    update_interval: float = 1.0  # seconds
    price_precision: int = 8
    value_precision: int = 2
    enable_alerts: bool = True
    enable_performance_tracking: bool = True
    history_retention_hours: int = 24
    volatility_window: int = 20  # periods for volatility calculation
    enable_risk_metrics: bool = True


@dataclass
class PortfolioMetrics:
    """Real-time portfolio metrics."""
    timestamp: datetime
    total_value: Decimal
    total_cost: Decimal
    total_return: Decimal
    return_percentage: float
    daily_pnl: Decimal
    daily_pnl_percentage: float
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_value": float(self.total_value),
            "total_cost": float(self.total_cost),
            "total_return": float(self.total_return),
            "return_percentage": self.return_percentage,
            "daily_pnl": float(self.daily_pnl),
            "daily_pnl_percentage": self.daily_pnl_percentage,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown
        }


@dataclass
class HoldingUpdate:
    """Real-time holding update."""
    symbol: str
    quantity: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percentage: float
    price_change_24h: Optional[float] = None
    volume_24h: Optional[Decimal] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RealTimePortfolioTracker:
    """Enhanced real-time portfolio tracking system."""
    
    def __init__(self, config: TrackingConfig = None):
        """Initialize the real-time tracker.
        
        Args:
            config: Tracking configuration
        """
        self.config = config or TrackingConfig()
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.price_feed_manager = PriceFeedManager()
        self.event_bus = StreamEventBus()
        
        # Current state
        self.current_holdings: Dict[str, PortfolioHolding] = {}
        self.current_prices: Dict[str, PriceUpdate] = {}
        self.current_metrics: Optional[PortfolioMetrics] = None
        
        # Historical data for analytics
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.value_history: deque = deque(maxlen=1000)
        self.metrics_history: deque = deque(maxlen=1000)
        
        # Tracking state
        self._running = False
        self._last_update = None
        self._update_task = None
        
        # Performance tracking
        self._daily_start_value: Optional[Decimal] = None
        self._session_start_value: Optional[Decimal] = None
        
        # Event handlers
        self.update_handlers: Set[Callable[[PortfolioMetrics], None]] = set()
        self.holding_handlers: Set[Callable[[str, HoldingUpdate], None]] = set()
        
    async def start(self, holdings: List[PortfolioHolding]):
        """Start real-time tracking.
        
        Args:
            holdings: Initial portfolio holdings
        """
        if self._running:
            logger.warning("Tracker is already running")
            return
        
        logger.info("Starting real-time portfolio tracker")
        
        # Initialize holdings
        self.current_holdings = {h.symbol: h for h in holdings}
        symbols = list(self.current_holdings.keys())
        
        # Start price feeds
        await self.price_feed_manager.start()
        await self.price_feed_manager.subscribe_symbols(symbols)
        self.price_feed_manager.add_handler(self._handle_price_update)
        
        # Initialize baseline values
        await self._initialize_baseline()
        
        # Start update loop
        self._running = True
        if self.config.mode == TrackingMode.CONTINUOUS:
            self._update_task = asyncio.create_task(self._continuous_update_loop())
        elif self.config.mode == TrackingMode.INTERVAL:
            self._update_task = asyncio.create_task(self._interval_update_loop())
        
        logger.info(f"Real-time tracking started for {len(symbols)} symbols")
    
    async def stop(self):
        """Stop real-time tracking."""
        if not self._running:
            return
        
        logger.info("Stopping real-time portfolio tracker")
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        await self.price_feed_manager.stop()
        
        logger.info("Real-time tracking stopped")
    
    def add_update_handler(self, handler: Callable[[PortfolioMetrics], None]):
        """Add portfolio update handler."""
        self.update_handlers.add(handler)
    
    def remove_update_handler(self, handler: Callable[[PortfolioMetrics], None]):
        """Remove portfolio update handler."""
        self.update_handlers.discard(handler)
    
    def add_holding_handler(self, handler: Callable[[str, HoldingUpdate], None]):
        """Add holding update handler."""
        self.holding_handlers.add(handler)
    
    def remove_holding_handler(self, handler: Callable[[str, HoldingUpdate], None]):
        """Remove holding update handler."""
        self.holding_handlers.discard(handler)
    
    async def add_holding(self, holding: PortfolioHolding):
        """Add new holding to track."""
        self.current_holdings[holding.symbol] = holding
        
        if self._running:
            await self.price_feed_manager.subscribe_symbols([holding.symbol])
            await self._update_portfolio_metrics()
    
    async def remove_holding(self, symbol: str):
        """Remove holding from tracking."""
        if symbol in self.current_holdings:
            del self.current_holdings[symbol]
            await self.price_feed_manager.unsubscribe_symbols([symbol])
            await self._update_portfolio_metrics()
    
    async def update_holding_quantity(self, symbol: str, new_quantity: Decimal):
        """Update holding quantity."""
        if symbol in self.current_holdings:
            self.current_holdings[symbol].quantity = new_quantity
            await self._update_portfolio_metrics()
    
    async def force_update(self):
        """Force immediate portfolio update."""
        await self._update_portfolio_metrics()
    
    def get_current_metrics(self) -> Optional[PortfolioMetrics]:
        """Get current portfolio metrics."""
        return self.current_metrics
    
    def get_holding_update(self, symbol: str) -> Optional[HoldingUpdate]:
        """Get current holding update."""
        if symbol not in self.current_holdings:
            return None
        
        holding = self.current_holdings[symbol]
        price_update = self.current_prices.get(symbol)
        
        if not price_update:
            return None
        
        market_value = holding.quantity * price_update.price
        unrealized_pnl = market_value - holding.cost_basis
        unrealized_pnl_pct = float(unrealized_pnl / holding.cost_basis * 100) if holding.cost_basis > 0 else 0
        
        return HoldingUpdate(
            symbol=symbol,
            quantity=holding.quantity,
            current_price=price_update.price,
            market_value=market_value,
            cost_basis=holding.cost_basis,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percentage=unrealized_pnl_pct,
            price_change_24h=price_update.change_percent_24h,
            volume_24h=price_update.volume_24h
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.current_metrics:
            return {}
        
        # Calculate additional metrics from history
        recent_values = list(self.value_history)[-20:]  # Last 20 updates
        volatility = None
        if len(recent_values) > 1:
            returns = [(float(recent_values[i]) - float(recent_values[i-1])) / float(recent_values[i-1]) 
                      for i in range(1, len(recent_values))]
            if returns:
                volatility = statistics.stdev(returns) * 100  # As percentage
        
        return {
            "current_metrics": self.current_metrics.to_dict(),
            "volatility": volatility,
            "tracking_duration": (datetime.now(timezone.utc) - self._last_update).total_seconds() if self._last_update else 0,
            "total_updates": len(self.metrics_history),
            "symbols_tracked": len(self.current_holdings),
            "last_update": self._last_update.isoformat() if self._last_update else None
        }
    
    async def _handle_price_update(self, price_update: PriceUpdate):
        """Handle incoming price update."""
        self.current_prices[price_update.symbol] = price_update
        
        # Store price history
        self.price_history[price_update.symbol].append({
            "timestamp": price_update.timestamp,
            "price": float(price_update.price),
            "volume": float(price_update.volume_24h) if price_update.volume_24h else None
        })
        
        # Update holding if we track this symbol
        if price_update.symbol in self.current_holdings:
            holding_update = self.get_holding_update(price_update.symbol)
            if holding_update:
                await self._notify_holding_handlers(price_update.symbol, holding_update)
        
        # Trigger portfolio update if in continuous mode
        if self.config.mode == TrackingMode.CONTINUOUS:
            await self._update_portfolio_metrics()
    
    async def _initialize_baseline(self):
        """Initialize baseline values for performance tracking."""
        current_snapshot = await self.portfolio_analyzer.create_portfolio_snapshot(
            list(self.current_holdings.values())
        )
        
        self._session_start_value = current_snapshot.total_value
        self._daily_start_value = current_snapshot.total_value  # In real app, load from daily start
        
        logger.info(f"Initialized baseline portfolio value: ${current_snapshot.total_value:,.2f}")
    
    async def _update_portfolio_metrics(self):
        """Update portfolio metrics."""
        try:
            # Create current snapshot
            current_snapshot = await self.portfolio_analyzer.create_portfolio_snapshot(
                list(self.current_holdings.values())
            )
            
            # Calculate metrics
            total_return = current_snapshot.total_value - current_snapshot.total_cost
            return_percentage = float(total_return / current_snapshot.total_cost * 100) if current_snapshot.total_cost > 0 else 0
            
            # Calculate daily P&L
            daily_pnl = Decimal("0")
            daily_pnl_percentage = 0.0
            if self._daily_start_value:
                daily_pnl = current_snapshot.total_value - self._daily_start_value
                daily_pnl_percentage = float(daily_pnl / self._daily_start_value * 100)
            
            # Create metrics object
            metrics = PortfolioMetrics(
                timestamp=datetime.now(timezone.utc),
                total_value=current_snapshot.total_value,
                total_cost=current_snapshot.total_cost,
                total_return=total_return,
                return_percentage=return_percentage,
                daily_pnl=daily_pnl,
                daily_pnl_percentage=daily_pnl_percentage
            )
            
            # Store history
            self.value_history.append(float(current_snapshot.total_value))
            self.metrics_history.append(metrics)
            
            # Update current metrics
            self.current_metrics = metrics
            self._last_update = metrics.timestamp
            
            # Notify handlers
            await self._notify_update_handlers(metrics)
            
            # Broadcast event
            event = StreamEvent(
                event_type=EventType.PORTFOLIO_UPDATE,
                data=metrics.to_dict(),
                source="realtime_tracker"
            )
            await self.event_bus.publish(event)
            
        except Exception as e:
            logger.error(f"Error updating portfolio metrics: {e}")
    
    async def _continuous_update_loop(self):
        """Continuous update loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.update_interval)
                if self._running:  # Check again after sleep
                    await self._update_portfolio_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous update loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _interval_update_loop(self):
        """Interval-based update loop."""
        while self._running:
            try:
                await self._update_portfolio_metrics()
                await asyncio.sleep(self.config.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in interval update loop: {e}")
                await asyncio.sleep(5)
    
    async def _notify_update_handlers(self, metrics: PortfolioMetrics):
        """Notify portfolio update handlers."""
        for handler in self.update_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(metrics))
                else:
                    handler(metrics)
            except Exception as e:
                logger.error(f"Error in portfolio update handler: {e}")
    
    async def _notify_holding_handlers(self, symbol: str, holding_update: HoldingUpdate):
        """Notify holding update handlers."""
        for handler in self.holding_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(symbol, holding_update))
                else:
                    handler(symbol, holding_update)
            except Exception as e:
                logger.error(f"Error in holding update handler: {e}")

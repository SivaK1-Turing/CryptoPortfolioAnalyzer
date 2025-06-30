"""Data models for portfolio analytics."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum


class PerformancePeriod(Enum):
    """Performance calculation periods."""
    DAY_1 = "1d"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    DAYS_365 = "1y"
    ALL_TIME = "all"


class RiskMetric(Enum):
    """Risk assessment metrics."""
    VOLATILITY = "volatility"
    VAR_95 = "var_95"
    VAR_99 = "var_99"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    BETA = "beta"


@dataclass
class PortfolioHolding:
    """Individual portfolio holding with current valuation."""
    
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    currency: str = "usd"
    purchase_date: Optional[datetime] = None
    
    @property
    def market_value(self) -> Decimal:
        """Current market value of holding."""
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> Decimal:
        """Total cost basis of holding."""
        return self.quantity * self.average_cost
    
    @property
    def unrealized_pnl(self) -> Decimal:
        """Unrealized profit/loss."""
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_percentage(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return float((self.unrealized_pnl / self.cost_basis) * 100)


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot at a specific point in time."""
    
    timestamp: datetime
    holdings: List[PortfolioHolding]
    total_value: Decimal
    total_cost: Decimal
    cash_balance: Decimal = Decimal("0")
    
    @property
    def total_unrealized_pnl(self) -> Decimal:
        """Total unrealized P&L across all holdings."""
        return sum(holding.unrealized_pnl for holding in self.holdings)
    
    @property
    def total_unrealized_pnl_percentage(self) -> float:
        """Total unrealized P&L percentage."""
        if self.total_cost == 0:
            return 0.0
        return float((self.total_unrealized_pnl / self.total_cost) * 100)
    
    @property
    def portfolio_value(self) -> Decimal:
        """Total portfolio value including cash."""
        return self.total_value + self.cash_balance


@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics for a specific period."""
    
    period: PerformancePeriod
    start_date: datetime
    end_date: datetime
    start_value: Decimal
    end_value: Decimal
    total_return: Decimal
    total_return_percentage: float
    annualized_return: float
    volatility: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    
    @property
    def days_elapsed(self) -> int:
        """Number of days in the performance period."""
        return (self.end_date - self.start_date).days


@dataclass
class RiskMetrics:
    """Risk assessment metrics for portfolio."""
    
    volatility_daily: float
    volatility_annualized: float
    var_95_daily: float
    var_99_daily: float
    var_95_monthly: float
    var_99_monthly: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    beta: Optional[float] = None
    correlation_with_market: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'volatility_daily': self.volatility_daily,
            'volatility_annualized': self.volatility_annualized,
            'var_95_daily': self.var_95_daily,
            'var_99_daily': self.var_99_daily,
            'var_95_monthly': self.var_95_monthly,
            'var_99_monthly': self.var_99_monthly,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'beta': self.beta,
            'correlation_with_market': self.correlation_with_market
        }


@dataclass
class AllocationMetrics:
    """Asset allocation analysis metrics."""
    
    allocations: Dict[str, float]  # symbol -> percentage
    concentration_risk: float
    diversification_ratio: float
    herfindahl_index: float
    effective_assets: float
    largest_position: float
    top_5_concentration: float
    rebalancing_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'allocations': self.allocations,
            'concentration_risk': self.concentration_risk,
            'diversification_ratio': self.diversification_ratio,
            'herfindahl_index': self.herfindahl_index,
            'effective_assets': self.effective_assets,
            'largest_position': self.largest_position,
            'top_5_concentration': self.top_5_concentration,
            'rebalancing_suggestions': self.rebalancing_suggestions
        }


@dataclass
class BenchmarkComparison:
    """Comparison against market benchmarks."""
    
    benchmark_name: str
    portfolio_return: float
    benchmark_return: float
    alpha: float
    beta: float
    correlation: float
    tracking_error: float
    information_ratio: float
    up_capture: float
    down_capture: float
    
    @property
    def outperformance(self) -> float:
        """Portfolio outperformance vs benchmark."""
        return self.portfolio_return - self.benchmark_return


@dataclass
class PortfolioAlert:
    """Portfolio monitoring alert."""
    
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    timestamp: datetime
    symbol: Optional[str] = None
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsReport:
    """Comprehensive analytics report."""
    
    report_id: str
    generated_at: datetime
    portfolio_snapshot: PortfolioSnapshot
    performance_metrics: Dict[PerformancePeriod, PerformanceMetrics]
    risk_metrics: RiskMetrics
    allocation_metrics: AllocationMetrics
    benchmark_comparisons: List[BenchmarkComparison]
    alerts: List[PortfolioAlert]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'report_id': self.report_id,
            'generated_at': self.generated_at.isoformat(),
            'portfolio_snapshot': {
                'timestamp': self.portfolio_snapshot.timestamp.isoformat(),
                'total_value': float(self.portfolio_snapshot.total_value),
                'total_cost': float(self.portfolio_snapshot.total_cost),
                'total_unrealized_pnl': float(self.portfolio_snapshot.total_unrealized_pnl),
                'total_unrealized_pnl_percentage': self.portfolio_snapshot.total_unrealized_pnl_percentage,
                'holdings_count': len(self.portfolio_snapshot.holdings)
            },
            'performance_metrics': {
                period.value: {
                    'total_return_percentage': metrics.total_return_percentage,
                    'annualized_return': metrics.annualized_return,
                    'volatility': metrics.volatility,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'max_drawdown': metrics.max_drawdown
                } for period, metrics in self.performance_metrics.items()
            },
            'risk_metrics': self.risk_metrics.to_dict(),
            'allocation_metrics': self.allocation_metrics.to_dict(),
            'benchmark_comparisons': [
                {
                    'benchmark_name': comp.benchmark_name,
                    'portfolio_return': comp.portfolio_return,
                    'benchmark_return': comp.benchmark_return,
                    'alpha': comp.alpha,
                    'beta': comp.beta,
                    'outperformance': comp.outperformance
                } for comp in self.benchmark_comparisons
            ],
            'alerts_count': len(self.alerts)
        }

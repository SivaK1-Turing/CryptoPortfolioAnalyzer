"""Tests for analytics data models."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.analytics.models import (
    PortfolioHolding,
    PortfolioSnapshot,
    PerformanceMetrics,
    RiskMetrics,
    AllocationMetrics,
    BenchmarkComparison,
    PortfolioAlert,
    AnalyticsReport,
    PerformancePeriod,
    RiskMetric
)


class TestPortfolioHolding:
    """Test PortfolioHolding model."""
    
    def test_portfolio_holding_creation(self):
        """Test creating a PortfolioHolding instance."""
        holding = PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("0.5"),
            average_cost=Decimal("45000.00"),
            current_price=Decimal("50000.00"),
            currency="usd"
        )
        
        assert holding.symbol == "BTC"
        assert holding.quantity == Decimal("0.5")
        assert holding.average_cost == Decimal("45000.00")
        assert holding.current_price == Decimal("50000.00")
        assert holding.currency == "usd"
    
    def test_portfolio_holding_market_value(self):
        """Test market value calculation."""
        holding = PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("2.0"),
            average_cost=Decimal("3000.00"),
            current_price=Decimal("3500.00")
        )
        
        assert holding.market_value == Decimal("7000.00")
    
    def test_portfolio_holding_cost_basis(self):
        """Test cost basis calculation."""
        holding = PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("1000"),
            average_cost=Decimal("1.20"),
            current_price=Decimal("1.50")
        )
        
        assert holding.cost_basis == Decimal("1200.00")
    
    def test_portfolio_holding_unrealized_pnl(self):
        """Test unrealized P&L calculation."""
        holding = PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.0"),
            average_cost=Decimal("40000.00"),
            current_price=Decimal("50000.00")
        )
        
        assert holding.unrealized_pnl == Decimal("10000.00")
        assert holding.unrealized_pnl_percentage == 25.0
    
    def test_portfolio_holding_unrealized_pnl_loss(self):
        """Test unrealized P&L calculation for losses."""
        holding = PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("1.0"),
            average_cost=Decimal("4000.00"),
            current_price=Decimal("3000.00")
        )
        
        assert holding.unrealized_pnl == Decimal("-1000.00")
        assert holding.unrealized_pnl_percentage == -25.0
    
    def test_portfolio_holding_zero_cost_basis(self):
        """Test handling of zero cost basis."""
        holding = PortfolioHolding(
            symbol="FREE",
            quantity=Decimal("100"),
            average_cost=Decimal("0.00"),
            current_price=Decimal("1.00")
        )
        
        assert holding.unrealized_pnl_percentage == 0.0


class TestPortfolioSnapshot:
    """Test PortfolioSnapshot model."""
    
    def test_portfolio_snapshot_creation(self):
        """Test creating a PortfolioSnapshot instance."""
        holdings = [
            PortfolioHolding("BTC", Decimal("0.5"), Decimal("45000"), Decimal("50000")),
            PortfolioHolding("ETH", Decimal("2.0"), Decimal("3000"), Decimal("3500"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("32000.00"),
            total_cost=Decimal("28500.00"),
            cash_balance=Decimal("5000.00")
        )
        
        assert len(snapshot.holdings) == 2
        assert snapshot.total_value == Decimal("32000.00")
        assert snapshot.total_cost == Decimal("28500.00")
        assert snapshot.cash_balance == Decimal("5000.00")
    
    def test_portfolio_snapshot_total_unrealized_pnl(self):
        """Test total unrealized P&L calculation."""
        holdings = [
            PortfolioHolding("BTC", Decimal("1.0"), Decimal("40000"), Decimal("50000")),  # +10000
            PortfolioHolding("ETH", Decimal("1.0"), Decimal("4000"), Decimal("3000"))     # -1000
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("53000.00"),
            total_cost=Decimal("44000.00")
        )
        
        assert snapshot.total_unrealized_pnl == Decimal("9000.00")
        assert abs(snapshot.total_unrealized_pnl_percentage - 20.45) < 0.01
    
    def test_portfolio_snapshot_portfolio_value(self):
        """Test total portfolio value including cash."""
        holdings = [
            PortfolioHolding("BTC", Decimal("1.0"), Decimal("50000"), Decimal("50000"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("50000.00"),
            total_cost=Decimal("50000.00"),
            cash_balance=Decimal("10000.00")
        )
        
        assert snapshot.portfolio_value == Decimal("60000.00")


class TestPerformanceMetrics:
    """Test PerformanceMetrics model."""
    
    def test_performance_metrics_creation(self):
        """Test creating PerformanceMetrics instance."""
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)
        
        metrics = PerformanceMetrics(
            period=PerformancePeriod.DAYS_30,
            start_date=start_date,
            end_date=end_date,
            start_value=Decimal("100000.00"),
            end_value=Decimal("110000.00"),
            total_return=Decimal("10000.00"),
            total_return_percentage=10.0,
            annualized_return=120.0,
            volatility=25.0,
            sharpe_ratio=1.5,
            max_drawdown=5.0,
            win_rate=65.0
        )
        
        assert metrics.period == PerformancePeriod.DAYS_30
        assert metrics.total_return_percentage == 10.0
        assert metrics.annualized_return == 120.0
        assert metrics.volatility == 25.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.max_drawdown == 5.0
        assert metrics.win_rate == 65.0
    
    def test_performance_metrics_days_elapsed(self):
        """Test days elapsed calculation."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        
        metrics = PerformanceMetrics(
            period=PerformancePeriod.DAYS_30,
            start_date=start_date,
            end_date=end_date,
            start_value=Decimal("100000"),
            end_value=Decimal("110000"),
            total_return=Decimal("10000"),
            total_return_percentage=10.0,
            annualized_return=120.0,
            volatility=25.0
        )
        
        assert metrics.days_elapsed == 30


class TestRiskMetrics:
    """Test RiskMetrics model."""
    
    def test_risk_metrics_creation(self):
        """Test creating RiskMetrics instance."""
        risk_metrics = RiskMetrics(
            volatility_daily=0.05,
            volatility_annualized=0.79,
            var_95_daily=-0.08,
            var_99_daily=-0.12,
            var_95_monthly=-0.18,
            var_99_monthly=-0.27,
            sharpe_ratio=1.2,
            sortino_ratio=1.8,
            max_drawdown=15.0,
            max_drawdown_duration=45,
            beta=1.1,
            correlation_with_market=0.85
        )
        
        assert risk_metrics.volatility_daily == 0.05
        assert risk_metrics.volatility_annualized == 0.79
        assert risk_metrics.var_95_daily == -0.08
        assert risk_metrics.sharpe_ratio == 1.2
        assert risk_metrics.beta == 1.1
    
    def test_risk_metrics_to_dict(self):
        """Test converting RiskMetrics to dictionary."""
        risk_metrics = RiskMetrics(
            volatility_daily=0.05,
            volatility_annualized=0.79,
            var_95_daily=-0.08,
            var_99_daily=-0.12,
            var_95_monthly=-0.18,
            var_99_monthly=-0.27,
            sharpe_ratio=1.2,
            sortino_ratio=1.8,
            max_drawdown=15.0,
            max_drawdown_duration=45
        )
        
        risk_dict = risk_metrics.to_dict()
        
        assert isinstance(risk_dict, dict)
        assert risk_dict['volatility_daily'] == 0.05
        assert risk_dict['sharpe_ratio'] == 1.2
        assert risk_dict['max_drawdown'] == 15.0


class TestAllocationMetrics:
    """Test AllocationMetrics model."""
    
    def test_allocation_metrics_creation(self):
        """Test creating AllocationMetrics instance."""
        allocations = {"BTC": 50.0, "ETH": 30.0, "ADA": 20.0}
        
        allocation_metrics = AllocationMetrics(
            allocations=allocations,
            concentration_risk=25.0,
            diversification_ratio=0.85,
            herfindahl_index=3800.0,
            effective_assets=2.6,
            largest_position=50.0,
            top_5_concentration=100.0
        )
        
        assert allocation_metrics.allocations == allocations
        assert allocation_metrics.concentration_risk == 25.0
        assert allocation_metrics.diversification_ratio == 0.85
        assert allocation_metrics.largest_position == 50.0
    
    def test_allocation_metrics_to_dict(self):
        """Test converting AllocationMetrics to dictionary."""
        allocations = {"BTC": 60.0, "ETH": 40.0}
        
        allocation_metrics = AllocationMetrics(
            allocations=allocations,
            concentration_risk=40.0,
            diversification_ratio=0.75,
            herfindahl_index=5200.0,
            effective_assets=1.9,
            largest_position=60.0,
            top_5_concentration=100.0
        )
        
        metrics_dict = allocation_metrics.to_dict()
        
        assert isinstance(metrics_dict, dict)
        assert metrics_dict['allocations'] == allocations
        assert metrics_dict['concentration_risk'] == 40.0
        assert metrics_dict['largest_position'] == 60.0


class TestBenchmarkComparison:
    """Test BenchmarkComparison model."""
    
    def test_benchmark_comparison_creation(self):
        """Test creating BenchmarkComparison instance."""
        comparison = BenchmarkComparison(
            benchmark_name="Bitcoin",
            portfolio_return=15.0,
            benchmark_return=12.0,
            alpha=2.5,
            beta=1.1,
            correlation=0.85,
            tracking_error=8.0,
            information_ratio=0.375,
            up_capture=105.0,
            down_capture=95.0
        )
        
        assert comparison.benchmark_name == "Bitcoin"
        assert comparison.portfolio_return == 15.0
        assert comparison.benchmark_return == 12.0
        assert comparison.alpha == 2.5
        assert comparison.beta == 1.1
    
    def test_benchmark_comparison_outperformance(self):
        """Test outperformance calculation."""
        comparison = BenchmarkComparison(
            benchmark_name="Ethereum",
            portfolio_return=20.0,
            benchmark_return=15.0,
            alpha=3.0,
            beta=1.2,
            correlation=0.9,
            tracking_error=6.0,
            information_ratio=0.5,
            up_capture=110.0,
            down_capture=90.0
        )
        
        assert comparison.outperformance == 5.0


class TestPortfolioAlert:
    """Test PortfolioAlert model."""
    
    def test_portfolio_alert_creation(self):
        """Test creating PortfolioAlert instance."""
        alert = PortfolioAlert(
            alert_type="price_drop",
            severity="high",
            message="BTC dropped below $45,000",
            timestamp=datetime.now(timezone.utc),
            symbol="BTC",
            current_value=44500.0,
            threshold_value=45000.0,
            metadata={"drop_percentage": 5.2}
        )
        
        assert alert.alert_type == "price_drop"
        assert alert.severity == "high"
        assert alert.symbol == "BTC"
        assert alert.current_value == 44500.0
        assert alert.metadata["drop_percentage"] == 5.2


class TestAnalyticsReport:
    """Test AnalyticsReport model."""
    
    def test_analytics_report_creation(self):
        """Test creating AnalyticsReport instance."""
        # Create sample data
        holdings = [
            PortfolioHolding("BTC", Decimal("1.0"), Decimal("45000"), Decimal("50000"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("50000"),
            total_cost=Decimal("45000")
        )
        
        performance_metrics = {
            PerformancePeriod.DAYS_30: PerformanceMetrics(
                period=PerformancePeriod.DAYS_30,
                start_date=datetime.now(timezone.utc) - timedelta(days=30),
                end_date=datetime.now(timezone.utc),
                start_value=Decimal("45000"),
                end_value=Decimal("50000"),
                total_return=Decimal("5000"),
                total_return_percentage=11.11,
                annualized_return=133.33,
                volatility=25.0
            )
        }
        
        risk_metrics = RiskMetrics(
            volatility_daily=0.05,
            volatility_annualized=0.79,
            var_95_daily=-0.08,
            var_99_daily=-0.12,
            var_95_monthly=-0.18,
            var_99_monthly=-0.27,
            sharpe_ratio=1.2,
            sortino_ratio=1.8,
            max_drawdown=15.0,
            max_drawdown_duration=45
        )
        
        allocation_metrics = AllocationMetrics(
            allocations={"BTC": 100.0},
            concentration_risk=100.0,
            diversification_ratio=1.0,
            herfindahl_index=10000.0,
            effective_assets=1.0,
            largest_position=100.0,
            top_5_concentration=100.0
        )
        
        report = AnalyticsReport(
            report_id="test_report_001",
            generated_at=datetime.now(timezone.utc),
            portfolio_snapshot=snapshot,
            performance_metrics=performance_metrics,
            risk_metrics=risk_metrics,
            allocation_metrics=allocation_metrics,
            benchmark_comparisons=[],
            alerts=[]
        )
        
        assert report.report_id == "test_report_001"
        assert len(report.portfolio_snapshot.holdings) == 1
        assert PerformancePeriod.DAYS_30 in report.performance_metrics
        assert report.risk_metrics.sharpe_ratio == 1.2
    
    def test_analytics_report_to_dict(self):
        """Test converting AnalyticsReport to dictionary."""
        # Create minimal report
        holdings = [
            PortfolioHolding("BTC", Decimal("1.0"), Decimal("50000"), Decimal("50000"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("50000"),
            total_cost=Decimal("50000")
        )
        
        risk_metrics = RiskMetrics(
            volatility_daily=0.05,
            volatility_annualized=0.79,
            var_95_daily=-0.08,
            var_99_daily=-0.12,
            var_95_monthly=-0.18,
            var_99_monthly=-0.27,
            sharpe_ratio=1.2,
            sortino_ratio=1.8,
            max_drawdown=15.0,
            max_drawdown_duration=45
        )
        
        allocation_metrics = AllocationMetrics(
            allocations={"BTC": 100.0},
            concentration_risk=100.0,
            diversification_ratio=1.0,
            herfindahl_index=10000.0,
            effective_assets=1.0,
            largest_position=100.0,
            top_5_concentration=100.0
        )
        
        report = AnalyticsReport(
            report_id="test_report_002",
            generated_at=datetime.now(timezone.utc),
            portfolio_snapshot=snapshot,
            performance_metrics={},
            risk_metrics=risk_metrics,
            allocation_metrics=allocation_metrics,
            benchmark_comparisons=[],
            alerts=[]
        )
        
        report_dict = report.to_dict()
        
        assert isinstance(report_dict, dict)
        assert report_dict['report_id'] == "test_report_002"
        assert 'portfolio_snapshot' in report_dict
        assert 'risk_metrics' in report_dict
        assert 'allocation_metrics' in report_dict


class TestEnums:
    """Test enum classes."""
    
    def test_performance_period_enum(self):
        """Test PerformancePeriod enum."""
        assert PerformancePeriod.DAY_1.value == "1d"
        assert PerformancePeriod.DAYS_7.value == "7d"
        assert PerformancePeriod.DAYS_30.value == "30d"
        assert PerformancePeriod.DAYS_90.value == "90d"
        assert PerformancePeriod.DAYS_365.value == "1y"
        assert PerformancePeriod.ALL_TIME.value == "all"
    
    def test_risk_metric_enum(self):
        """Test RiskMetric enum."""
        assert RiskMetric.VOLATILITY.value == "volatility"
        assert RiskMetric.VAR_95.value == "var_95"
        assert RiskMetric.VAR_99.value == "var_99"
        assert RiskMetric.SHARPE_RATIO.value == "sharpe_ratio"
        assert RiskMetric.SORTINO_RATIO.value == "sortino_ratio"
        assert RiskMetric.MAX_DRAWDOWN.value == "max_drawdown"
        assert RiskMetric.BETA.value == "beta"

"""Tests for portfolio analyzer."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.analytics.portfolio import PortfolioAnalyzer
from crypto_portfolio_analyzer.analytics.models import (
    PortfolioHolding, PortfolioSnapshot, PerformanceMetrics, PerformancePeriod
)
from crypto_portfolio_analyzer.data.models import CryptocurrencyPrice, DataSource


@pytest.fixture
def sample_holdings_data():
    """Sample holdings data for testing."""
    return [
        {
            'symbol': 'BTC',
            'quantity': 0.5,
            'average_cost': 45000.0,
            'purchase_date': datetime(2024, 1, 1, tzinfo=timezone.utc)
        },
        {
            'symbol': 'ETH',
            'quantity': 2.0,
            'average_cost': 3000.0,
            'purchase_date': datetime(2024, 1, 15, tzinfo=timezone.utc)
        },
        {
            'symbol': 'ADA',
            'quantity': 1000,
            'average_cost': 1.2,
            'cash_balance': 5000.0
        }
    ]


@pytest.fixture
def mock_price_data():
    """Mock price data for testing."""
    return [
        CryptocurrencyPrice(
            symbol="BTC",
            name="Bitcoin",
            current_price=Decimal("50000.00"),
            currency="usd",
            data_source=DataSource.COINGECKO
        ),
        CryptocurrencyPrice(
            symbol="ETH",
            name="Ethereum",
            current_price=Decimal("3500.00"),
            currency="usd",
            data_source=DataSource.COINGECKO
        ),
        CryptocurrencyPrice(
            symbol="ADA",
            name="Cardano",
            current_price=Decimal("1.50"),
            currency="usd",
            data_source=DataSource.COINGECKO
        )
    ]


@pytest.fixture
def sample_historical_snapshots():
    """Sample historical snapshots for testing."""
    base_date = datetime.now(timezone.utc) - timedelta(days=30)
    snapshots = []
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        # Simulate portfolio growth with some volatility
        base_value = 50000 + (i * 100) + ((-1) ** i * 500)  # Growth with volatility
        
        holdings = [
            PortfolioHolding("BTC", Decimal("0.5"), Decimal("45000"), Decimal(str(base_value * 0.5))),
            PortfolioHolding("ETH", Decimal("2.0"), Decimal("3000"), Decimal(str(base_value * 0.35))),
            PortfolioHolding("ADA", Decimal("1000"), Decimal("1.2"), Decimal(str(base_value * 0.15)))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=date,
            holdings=holdings,
            total_value=Decimal(str(base_value)),
            total_cost=Decimal("28200"),  # 0.5*45000 + 2*3000 + 1000*1.2
            cash_balance=Decimal("5000")
        )
        snapshots.append(snapshot)
    
    return snapshots


class TestPortfolioAnalyzer:
    """Test PortfolioAnalyzer functionality."""
    
    @pytest.mark.asyncio
    async def test_create_portfolio_snapshot(self, sample_holdings_data, mock_price_data):
        """Test creating portfolio snapshot with live prices."""
        # Mock data service
        mock_data_service = AsyncMock()
        mock_data_service.get_multiple_prices.return_value = mock_price_data

        # Mock the get_data_service function to return our mock
        with patch('crypto_portfolio_analyzer.data.service.get_data_service') as mock_get_service:
            mock_get_service.return_value = mock_data_service

            analyzer = PortfolioAnalyzer(mock_data_service)

            snapshot = await analyzer.create_portfolio_snapshot(sample_holdings_data)

            assert isinstance(snapshot, PortfolioSnapshot)
            assert len(snapshot.holdings) == 3
            assert snapshot.holdings[0].symbol == "BTC"
            assert snapshot.holdings[0].current_price == Decimal("50000.00")
            assert snapshot.holdings[1].symbol == "ETH"
            assert snapshot.holdings[1].current_price == Decimal("3500.00")
            assert snapshot.holdings[2].symbol == "ADA"
            assert snapshot.holdings[2].current_price == Decimal("1.50")

            # Verify total calculations
            expected_total_value = (Decimal("0.5") * Decimal("50000") +
                                   Decimal("2.0") * Decimal("3500") +
                                   Decimal("1000") * Decimal("1.50"))
            assert snapshot.total_value == expected_total_value

            expected_total_cost = (Decimal("0.5") * Decimal("45000") +
                                  Decimal("2.0") * Decimal("3000") +
                                  Decimal("1000") * Decimal("1.2"))
            assert snapshot.total_cost == expected_total_cost
    
    @pytest.mark.asyncio
    async def test_create_portfolio_snapshot_empty_holdings(self):
        """Test creating portfolio snapshot with empty holdings."""
        mock_data_service = AsyncMock()
        mock_data_service.get_multiple_prices.return_value = []
        
        analyzer = PortfolioAnalyzer(mock_data_service)
        
        snapshot = await analyzer.create_portfolio_snapshot([])
        
        assert isinstance(snapshot, PortfolioSnapshot)
        assert len(snapshot.holdings) == 0
        assert snapshot.total_value == Decimal("0")
        assert snapshot.total_cost == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_30_days(self, sample_historical_snapshots):
        """Test calculating 30-day performance metrics."""
        analyzer = PortfolioAnalyzer()
        
        current_snapshot = sample_historical_snapshots[-1]  # Latest snapshot
        historical_snapshots = sample_historical_snapshots[:-1]  # All but latest
        
        metrics = await analyzer.calculate_performance_metrics(
            current_snapshot, historical_snapshots, PerformancePeriod.DAYS_30
        )
        
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.period == PerformancePeriod.DAYS_30
        assert metrics.start_value > 0
        assert metrics.end_value > 0
        assert isinstance(metrics.total_return_percentage, float)
        assert isinstance(metrics.annualized_return, float)
        assert isinstance(metrics.volatility, float)
        assert metrics.days_elapsed > 0
    
    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_7_days(self, sample_historical_snapshots):
        """Test calculating 7-day performance metrics."""
        analyzer = PortfolioAnalyzer()
        
        current_snapshot = sample_historical_snapshots[-1]
        historical_snapshots = sample_historical_snapshots
        
        metrics = await analyzer.calculate_performance_metrics(
            current_snapshot, historical_snapshots, PerformancePeriod.DAYS_7
        )
        
        assert metrics.period == PerformancePeriod.DAYS_7
        assert metrics.start_date <= metrics.end_date
        assert (metrics.end_date - metrics.start_date).days <= 7
    
    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_no_historical_data(self):
        """Test calculating performance metrics with no historical data."""
        analyzer = PortfolioAnalyzer()
        
        current_snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=[],
            total_value=Decimal("50000"),
            total_cost=Decimal("45000")
        )
        
        metrics = await analyzer.calculate_performance_metrics(
            current_snapshot, [], PerformancePeriod.DAYS_30
        )
        
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return_percentage == 0.0
        assert metrics.volatility == 0.0
    
    @pytest.mark.asyncio
    async def test_calculate_time_weighted_return(self, sample_historical_snapshots):
        """Test calculating time-weighted return with cash flows."""
        analyzer = PortfolioAnalyzer()
        
        # Sample cash flows
        cash_flows = [
            {
                'date': sample_historical_snapshots[10].timestamp,
                'amount': 10000,
                'type': 'deposit'
            },
            {
                'date': sample_historical_snapshots[20].timestamp,
                'amount': -5000,
                'type': 'withdrawal'
            }
        ]
        
        twr = await analyzer.calculate_time_weighted_return(sample_historical_snapshots, cash_flows)
        
        assert isinstance(twr, float)
        # Time-weighted return should be different from simple return due to cash flows
    
    @pytest.mark.asyncio
    async def test_calculate_time_weighted_return_no_cash_flows(self, sample_historical_snapshots):
        """Test calculating time-weighted return with no cash flows."""
        analyzer = PortfolioAnalyzer()
        
        twr = await analyzer.calculate_time_weighted_return(sample_historical_snapshots, [])
        
        assert isinstance(twr, float)
    
    @pytest.mark.asyncio
    async def test_calculate_time_weighted_return_insufficient_data(self):
        """Test calculating time-weighted return with insufficient data."""
        analyzer = PortfolioAnalyzer()
        
        single_snapshot = [PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=[],
            total_value=Decimal("50000"),
            total_cost=Decimal("45000")
        )]
        
        twr = await analyzer.calculate_time_weighted_return(single_snapshot, [])
        
        assert twr == 0.0
    
    def test_find_closest_snapshot(self, sample_historical_snapshots):
        """Test finding closest snapshot to target date."""
        analyzer = PortfolioAnalyzer()
        
        target_date = sample_historical_snapshots[15].timestamp + timedelta(hours=6)
        
        closest = analyzer._find_closest_snapshot(sample_historical_snapshots, target_date)
        
        assert closest is not None
        # Should find snapshot 15 or 16 (closest to target)
        assert closest in sample_historical_snapshots
    
    def test_find_closest_snapshot_empty_list(self):
        """Test finding closest snapshot with empty list."""
        analyzer = PortfolioAnalyzer()
        
        target_date = datetime.now(timezone.utc)
        closest = analyzer._find_closest_snapshot([], target_date)
        
        assert closest is None
    
    def test_calculate_annualized_return(self):
        """Test annualized return calculation."""
        analyzer = PortfolioAnalyzer()
        
        # Test 30-day period with 10% return
        annualized = analyzer._calculate_annualized_return(10.0, 30)
        assert annualized > 10.0  # Should be higher when annualized
        
        # Test 365-day period with 10% return
        annualized_yearly = analyzer._calculate_annualized_return(10.0, 365)
        assert abs(annualized_yearly - 10.0) < 0.1  # Should be close to 10%
        
        # Test zero days
        zero_days = analyzer._calculate_annualized_return(10.0, 0)
        assert zero_days == 0.0
    
    def test_calculate_daily_returns(self, sample_historical_snapshots):
        """Test daily returns calculation."""
        analyzer = PortfolioAnalyzer()
        
        start_date = sample_historical_snapshots[0].timestamp
        end_date = sample_historical_snapshots[-1].timestamp
        
        daily_returns = analyzer._calculate_daily_returns(
            sample_historical_snapshots, start_date, end_date
        )
        
        assert isinstance(daily_returns, list)
        assert len(daily_returns) > 0
        assert all(isinstance(r, float) for r in daily_returns)
        # Should have one less return than snapshots (first snapshot has no previous)
        assert len(daily_returns) == len(sample_historical_snapshots) - 1
    
    def test_calculate_daily_returns_insufficient_data(self):
        """Test daily returns calculation with insufficient data."""
        analyzer = PortfolioAnalyzer()
        
        single_snapshot = [PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=[],
            total_value=Decimal("50000"),
            total_cost=Decimal("45000")
        )]
        
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        daily_returns = analyzer._calculate_daily_returns(single_snapshot, start_date, end_date)
        
        assert daily_returns == []
    
    def test_calculate_max_drawdown(self, sample_historical_snapshots):
        """Test maximum drawdown calculation."""
        analyzer = PortfolioAnalyzer()
        
        start_date = sample_historical_snapshots[0].timestamp
        end_date = sample_historical_snapshots[-1].timestamp
        
        max_drawdown = analyzer._calculate_max_drawdown(
            sample_historical_snapshots, start_date, end_date
        )
        
        assert isinstance(max_drawdown, float)
        assert max_drawdown >= 0.0  # Drawdown should be positive percentage
        assert max_drawdown <= 100.0  # Cannot exceed 100%
    
    def test_calculate_max_drawdown_insufficient_data(self):
        """Test maximum drawdown calculation with insufficient data."""
        analyzer = PortfolioAnalyzer()
        
        single_snapshot = [PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=[],
            total_value=Decimal("50000"),
            total_cost=Decimal("45000")
        )]
        
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        max_drawdown = analyzer._calculate_max_drawdown(single_snapshot, start_date, end_date)
        
        assert max_drawdown is None
    
    def test_calculate_win_rate(self):
        """Test win rate calculation."""
        analyzer = PortfolioAnalyzer()
        
        # Test with mixed returns
        daily_returns = [0.02, -0.01, 0.03, -0.005, 0.01, -0.02, 0.015]
        win_rate = analyzer._calculate_win_rate(daily_returns)
        
        # 4 positive out of 7 returns = 57.14%
        expected_win_rate = (4 / 7) * 100
        assert abs(win_rate - expected_win_rate) < 0.01
    
    def test_calculate_win_rate_empty_returns(self):
        """Test win rate calculation with empty returns."""
        analyzer = PortfolioAnalyzer()
        
        win_rate = analyzer._calculate_win_rate([])
        assert win_rate is None
    
    def test_calculate_win_rate_all_positive(self):
        """Test win rate calculation with all positive returns."""
        analyzer = PortfolioAnalyzer()
        
        daily_returns = [0.01, 0.02, 0.005, 0.03]
        win_rate = analyzer._calculate_win_rate(daily_returns)
        
        assert win_rate == 100.0
    
    def test_calculate_win_rate_all_negative(self):
        """Test win rate calculation with all negative returns."""
        analyzer = PortfolioAnalyzer()
        
        daily_returns = [-0.01, -0.02, -0.005, -0.03]
        win_rate = analyzer._calculate_win_rate(daily_returns)
        
        assert win_rate == 0.0

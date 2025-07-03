"""Tests for visualization chart generation."""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import plotly.graph_objects as go

from crypto_portfolio_analyzer.visualization.charts import ChartGenerator
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding
from crypto_portfolio_analyzer.data.models import HistoricalPrice, DataSource


@pytest.fixture
def sample_portfolio_snapshot():
    """Sample portfolio snapshot for testing."""
    holdings = [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("0.5"),
            average_cost=Decimal("45000"),
            current_price=Decimal("50000")
        ),
        PortfolioHolding(
            symbol="ETH", 
            quantity=Decimal("2.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3500")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("1000"),
            average_cost=Decimal("1.2"),
            current_price=Decimal("1.5")
        )
    ]
    
    return PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=holdings,
        total_value=Decimal("32500"),
        total_cost=Decimal("28200"),
        cash_balance=Decimal("5000")
    )


@pytest.fixture
def sample_historical_snapshots():
    """Sample historical snapshots for testing."""
    snapshots = []
    base_date = datetime.now(timezone.utc) - timedelta(days=30)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        value = 30000 + (i * 100) + ((-1) ** i * 200)  # Trending up with volatility
        
        holdings = [
            PortfolioHolding("BTC", Decimal("0.5"), Decimal("45000"), Decimal(str(value * 0.6))),
            PortfolioHolding("ETH", Decimal("2.0"), Decimal("3000"), Decimal(str(value * 0.4)))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=date,
            holdings=holdings,
            total_value=Decimal(str(value)),
            total_cost=Decimal("28200")
        )
        snapshots.append(snapshot)
    
    return snapshots


@pytest.fixture
def sample_historical_prices():
    """Sample historical price data for testing."""
    prices = []
    base_date = datetime.now(timezone.utc) - timedelta(days=30)
    base_price = 50000
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        price = base_price + (i * 100) + ((-1) ** i * 500)  # Trending up with volatility
        
        historical_price = HistoricalPrice(
            symbol="BTC",
            timestamp=date,
            price=Decimal(str(price)),
            volume=Decimal("1000000"),
            data_source=DataSource.COINGECKO
        )
        prices.append(historical_price)
    
    return prices


class TestChartGenerator:
    """Test ChartGenerator functionality."""
    
    def test_chart_generator_initialization(self):
        """Test ChartGenerator initialization."""
        generator = ChartGenerator()
        
        assert generator.default_colors is not None
        assert generator.default_layout is not None
        assert 'primary' in generator.default_colors
        assert 'template' in generator.default_layout
    
    def test_create_portfolio_performance_chart(self, sample_historical_snapshots):
        """Test portfolio performance chart creation."""
        generator = ChartGenerator()
        
        fig = generator.create_portfolio_performance_chart(sample_historical_snapshots)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2  # Should have portfolio value and cost basis traces
        assert fig.layout.title.text == "Portfolio Performance"
    
    def test_create_portfolio_performance_chart_empty_data(self):
        """Test portfolio performance chart with empty data."""
        generator = ChartGenerator()
        
        fig = generator.create_portfolio_performance_chart([])
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0  # Should have "no data" annotation
    
    def test_create_allocation_pie_chart(self, sample_portfolio_snapshot):
        """Test allocation pie chart creation."""
        generator = ChartGenerator()
        
        fig = generator.create_allocation_pie_chart(sample_portfolio_snapshot)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1  # Should have one pie chart
        assert fig.data[0].type == 'pie'
        assert len(fig.data[0].labels) == 4  # 3 holdings + cash
        assert fig.layout.title.text == "Portfolio Allocation"
    
    def test_create_allocation_pie_chart_empty_holdings(self):
        """Test allocation pie chart with empty holdings."""
        generator = ChartGenerator()
        
        empty_snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=[],
            total_value=Decimal("0"),
            total_cost=Decimal("0")
        )
        
        fig = generator.create_allocation_pie_chart(empty_snapshot)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0  # Should have "no data" annotation
    
    def test_create_candlestick_chart(self, sample_historical_prices):
        """Test candlestick chart creation."""
        generator = ChartGenerator()
        
        fig = generator.create_candlestick_chart(sample_historical_prices, "BTC")
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2  # Should have candlestick and volume traces
        assert fig.data[0].type == 'candlestick'
        assert fig.layout.title.text == "BTC Price Chart"
    
    def test_create_candlestick_chart_with_indicators(self, sample_historical_prices):
        """Test candlestick chart with technical indicators."""
        generator = ChartGenerator()
        
        # Mock indicators
        indicators = {
            'SMA_20': [50000] * len(sample_historical_prices),
            'RSI': [50] * len(sample_historical_prices)
        }
        
        fig = generator.create_candlestick_chart(sample_historical_prices, "BTC", indicators)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 4  # Candlestick, volume, and 2 indicators
    
    def test_create_candlestick_chart_empty_data(self):
        """Test candlestick chart with empty data."""
        generator = ChartGenerator()
        
        fig = generator.create_candlestick_chart([], "BTC")
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0  # Should have "no data" annotation
    
    def test_create_performance_comparison_chart(self):
        """Test performance comparison chart creation."""
        generator = ChartGenerator()
        
        # Sample performance data
        base_date = datetime.now(timezone.utc) - timedelta(days=10)
        performance_data = {
            'Portfolio': [(base_date + timedelta(days=i), i * 2) for i in range(10)],
            'BTC': [(base_date + timedelta(days=i), i * 1.5) for i in range(10)],
            'ETH': [(base_date + timedelta(days=i), i * 1.8) for i in range(10)]
        }
        
        fig = generator.create_performance_comparison_chart(performance_data)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 3  # Three performance lines
        assert fig.layout.title.text == "Performance Comparison"
    
    def test_create_performance_comparison_chart_empty_data(self):
        """Test performance comparison chart with empty data."""
        generator = ChartGenerator()
        
        fig = generator.create_performance_comparison_chart({})
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0  # Should have "no data" annotation
    
    def test_create_risk_return_scatter(self):
        """Test risk vs return scatter plot creation."""
        generator = ChartGenerator()
        
        risk_return_data = [
            {'name': 'BTC', 'risk': 25.0, 'return': 15.0, 'size': 30},
            {'name': 'ETH', 'risk': 30.0, 'return': 20.0, 'size': 25},
            {'name': 'ADA', 'risk': 35.0, 'return': 10.0, 'size': 20}
        ]
        
        fig = generator.create_risk_return_scatter(risk_return_data)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1  # One scatter plot
        assert fig.data[0].type == 'scatter'
        assert len(fig.data[0].x) == 3  # Three data points
        assert fig.layout.title.text == "Risk vs Return Analysis"
    
    def test_create_risk_return_scatter_empty_data(self):
        """Test risk vs return scatter with empty data."""
        generator = ChartGenerator()
        
        fig = generator.create_risk_return_scatter([])
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0  # Should have "no data" annotation
    
    def test_update_chart_theme(self):
        """Test chart theme updating."""
        generator = ChartGenerator()
        
        # Test dark theme
        generator.update_chart_theme('plotly_dark')
        assert generator.default_layout['template'] == 'plotly_dark'
        assert generator.default_colors['background'] == '#2f2f2f'
        
        # Test light theme
        generator.update_chart_theme('plotly_white')
        assert generator.default_layout['template'] == 'plotly_white'
        assert generator.default_colors['background'] == '#ffffff'
    
    def test_get_chart_config(self):
        """Test chart configuration retrieval."""
        generator = ChartGenerator()
        
        config = generator.get_chart_config()
        
        assert isinstance(config, dict)
        assert 'displayModeBar' in config
        assert 'toImageButtonOptions' in config
        assert config['displaylogo'] is False
    
    def test_create_empty_chart(self):
        """Test empty chart creation."""
        generator = ChartGenerator()
        
        fig = generator._create_empty_chart("Test message")
        
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) == 1
        assert fig.layout.annotations[0].text == "Test message"
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False


class TestChartGeneratorEdgeCases:
    """Test edge cases and error handling."""
    
    def test_portfolio_performance_single_snapshot(self, sample_portfolio_snapshot):
        """Test portfolio performance chart with single snapshot."""
        generator = ChartGenerator()
        
        fig = generator.create_portfolio_performance_chart([sample_portfolio_snapshot])
        
        assert isinstance(fig, go.Figure)
        # Should handle single point gracefully
    
    def test_allocation_chart_zero_values(self):
        """Test allocation chart with zero values."""
        generator = ChartGenerator()
        
        holdings = [
            PortfolioHolding("BTC", Decimal("0"), Decimal("0"), Decimal("0")),
            PortfolioHolding("ETH", Decimal("0"), Decimal("0"), Decimal("0"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("0"),
            total_cost=Decimal("0")
        )
        
        fig = generator.create_allocation_pie_chart(snapshot)
        
        assert isinstance(fig, go.Figure)
        # Should handle zero values gracefully
    
    def test_candlestick_chart_missing_ohlc_data(self):
        """Test candlestick chart with missing OHLC data."""
        generator = ChartGenerator()
        
        # Create price data with missing volume
        prices = [
            HistoricalPrice(
                symbol="BTC",
                timestamp=datetime.now(timezone.utc),
                price=Decimal("50000"),
                volume=None,
                data_source=DataSource.COINGECKO
            )
        ]
        
        fig = generator.create_candlestick_chart(prices, "BTC")
        
        assert isinstance(fig, go.Figure)
        # Should handle missing volume gracefully
    
    def test_performance_comparison_mismatched_data(self):
        """Test performance comparison with mismatched data lengths."""
        generator = ChartGenerator()
        
        base_date = datetime.now(timezone.utc)
        performance_data = {
            'Short': [(base_date, 1.0), (base_date + timedelta(days=1), 2.0)],
            'Long': [(base_date + timedelta(days=i), i) for i in range(10)]
        }
        
        fig = generator.create_performance_comparison_chart(performance_data)
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2  # Should handle different lengths
    
    def test_risk_return_scatter_missing_fields(self):
        """Test risk return scatter with missing fields."""
        generator = ChartGenerator()
        
        risk_return_data = [
            {'name': 'BTC', 'risk': 25.0, 'return': 15.0},  # Missing size
            {'name': 'ETH', 'risk': 30.0, 'return': 20.0, 'size': 25}
        ]
        
        fig = generator.create_risk_return_scatter(risk_return_data)
        
        assert isinstance(fig, go.Figure)
        # Should use default size for missing values
    
    def test_chart_with_nan_values(self, sample_historical_snapshots):
        """Test chart generation with NaN values."""
        generator = ChartGenerator()
        
        # Introduce NaN values
        sample_historical_snapshots[5].total_value = Decimal('nan')
        
        fig = generator.create_portfolio_performance_chart(sample_historical_snapshots)
        
        assert isinstance(fig, go.Figure)
        # Should handle NaN values gracefully
    
    def test_chart_with_extreme_values(self):
        """Test chart generation with extreme values."""
        generator = ChartGenerator()
        
        # Create data with extreme values
        holdings = [
            PortfolioHolding("BTC", Decimal("0.000001"), Decimal("1000000"), Decimal("999999999"))
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=Decimal("999999999"),
            total_cost=Decimal("1")
        )
        
        fig = generator.create_allocation_pie_chart(snapshot)
        
        assert isinstance(fig, go.Figure)
        # Should handle extreme values gracefully

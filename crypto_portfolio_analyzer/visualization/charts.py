"""Interactive chart generation using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import base64
from io import BytesIO

from ..analytics.models import PortfolioSnapshot, PortfolioHolding, PerformanceMetrics
from ..data.models import HistoricalPrice

logger = logging.getLogger(__name__)


class ChartType(Enum):
    """Chart type enumeration."""
    LINE = "line"
    CANDLESTICK = "candlestick"
    PIE = "pie"
    BAR = "bar"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    WATERFALL = "waterfall"


class ExportFormat(Enum):
    """Chart export format enumeration."""
    HTML = "html"
    PNG = "png"
    JPG = "jpg"
    PDF = "pdf"
    SVG = "svg"
    JSON = "json"


@dataclass
class ChartConfig:
    """Chart configuration settings."""
    chart_type: ChartType
    title: str = ""
    width: int = 800
    height: int = 600
    theme: str = "plotly_white"
    colors: Dict[str, str] = field(default_factory=dict)
    show_legend: bool = True
    interactive: bool = True
    export_format: Optional[ExportFormat] = None
    custom_layout: Dict[str, Any] = field(default_factory=dict)


class BaseChart:
    """Base class for all chart types."""

    def __init__(self, config: ChartConfig):
        """Initialize base chart.

        Args:
            config: Chart configuration
        """
        self.config = config
        self.figure = None
        self._data = None

    def create(self, data: Any) -> go.Figure:
        """Create the chart with provided data.

        Args:
            data: Chart data

        Returns:
            Plotly figure object
        """
        raise NotImplementedError("Subclasses must implement create method")

    def export(self, filename: str, format: Optional[ExportFormat] = None) -> str:
        """Export chart to file.

        Args:
            filename: Output filename
            format: Export format (defaults to config format)

        Returns:
            Path to exported file
        """
        if not self.figure:
            raise ValueError("Chart must be created before export")

        export_format = format or self.config.export_format or ExportFormat.HTML

        if export_format == ExportFormat.HTML:
            self.figure.write_html(filename)
        elif export_format == ExportFormat.PNG:
            self.figure.write_image(filename, format="png")
        elif export_format == ExportFormat.JPG:
            self.figure.write_image(filename, format="jpg")
        elif export_format == ExportFormat.PDF:
            self.figure.write_image(filename, format="pdf")
        elif export_format == ExportFormat.SVG:
            self.figure.write_image(filename, format="svg")
        elif export_format == ExportFormat.JSON:
            with open(filename, 'w') as f:
                json.dump(self.figure.to_dict(), f, indent=2)

        return filename

    def to_html(self) -> str:
        """Convert chart to HTML string.

        Returns:
            HTML representation of chart
        """
        if not self.figure:
            raise ValueError("Chart must be created before conversion")
        return self.figure.to_html()

    def to_json(self) -> str:
        """Convert chart to JSON string.

        Returns:
            JSON representation of chart
        """
        if not self.figure:
            raise ValueError("Chart must be created before conversion")
        return self.figure.to_json()


class ChartManager:
    """Manages chart creation and configuration."""

    def __init__(self):
        """Initialize chart manager."""
        self.default_colors = {
            'primary': '#1f77b4',
            'secondary': '#ff7f0e',
            'success': '#2ca02c',
            'danger': '#d62728',
            'warning': '#ff7f0e',
            'info': '#17a2b8',
            'background': '#ffffff',
            'grid': '#e6e6e6',
            'crypto': {
                'BTC': '#f7931a',
                'ETH': '#627eea',
                'ADA': '#0033ad',
                'DOT': '#e6007a',
                'LINK': '#375bd2'
            }
        }

        self.default_layout = {
            'template': 'plotly_white',
            'font': {'family': 'Arial, sans-serif', 'size': 12},
            'margin': {'l': 50, 'r': 50, 't': 50, 'b': 50},
            'showlegend': True,
            'hovermode': 'x unified'
        }

        self.chart_registry = {}

    def register_chart(self, name: str, chart_class: type):
        """Register a chart class.

        Args:
            name: Chart name
            chart_class: Chart class
        """
        self.chart_registry[name] = chart_class

    def create_chart(self, chart_type: str, config: ChartConfig, data: Any) -> BaseChart:
        """Create a chart of specified type.

        Args:
            chart_type: Type of chart to create
            config: Chart configuration
            data: Chart data

        Returns:
            Created chart instance
        """
        if chart_type not in self.chart_registry:
            raise ValueError(f"Unknown chart type: {chart_type}")

        chart_class = self.chart_registry[chart_type]
        chart = chart_class(config)
        chart.create(data)
        return chart


class ChartGenerator(ChartManager):
    """Interactive chart generation engine using Plotly."""

    def __init__(self):
        """Initialize chart generator."""
        super().__init__()

        # Register built-in chart types
        self.register_chart('portfolio_performance', PortfolioChart)
        self.register_chart('price_chart', PriceChart)
        self.register_chart('allocation', AllocationChart)
        self.register_chart('performance', PerformanceChart)
        self.register_chart('technical', TechnicalChart)


class PortfolioChart(BaseChart):
    """Portfolio performance chart."""

    def create(self, snapshots: List[PortfolioSnapshot]) -> go.Figure:
        """Create portfolio performance chart.

        Args:
            snapshots: List of portfolio snapshots over time

        Returns:
            Plotly figure object
        """
        if not snapshots:
            self.figure = self._create_empty_chart("No portfolio data available")
            return self.figure

        # Sort snapshots by timestamp
        sorted_snapshots = sorted(snapshots, key=lambda x: x.timestamp)

        # Extract data
        timestamps = [s.timestamp for s in sorted_snapshots]
        portfolio_values = [float(s.portfolio_value) for s in sorted_snapshots]
        cost_basis = [float(s.total_cost) for s in sorted_snapshots]

        # Calculate returns
        initial_value = portfolio_values[0] if portfolio_values else 0
        returns = [(value / initial_value - 1) * 100 if initial_value > 0 else 0
                  for value in portfolio_values]

        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Portfolio Value', 'Cumulative Return (%)'),
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3]
        )

        # Portfolio value line
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=portfolio_values,
                mode='lines',
                name='Portfolio Value',
                line=dict(color='#1f77b4', width=2),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Date: %{x}<br>' +
                             'Value: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Cost basis line
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=cost_basis,
                mode='lines',
                name='Cost Basis',
                line=dict(color='#ff7f0e', width=1, dash='dash'),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Date: %{x}<br>' +
                             'Value: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Returns line
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=returns,
                mode='lines',
                name='Cumulative Return',
                line=dict(color='#2ca02c', width=2),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Date: %{x}<br>' +
                             'Return: %{y:.2f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )

        # Add zero line for returns
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        # Update layout
        fig.update_layout(
            title=self.config.title or "Portfolio Performance",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width,
            showlegend=self.config.show_legend
        )

        # Update y-axes
        fig.update_yaxes(title_text="Value ($)", row=1, col=1)
        fig.update_yaxes(title_text="Return (%)", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)

        self.figure = fig
        return fig

    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title=self.config.title or "Portfolio Performance",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width
        )
        return fig


class AllocationChart(BaseChart):
    """Portfolio allocation chart."""

    def create(self, portfolio_snapshot: PortfolioSnapshot) -> go.Figure:
        """Create portfolio allocation pie chart.

        Args:
            portfolio_snapshot: Current portfolio snapshot

        Returns:
            Plotly figure object
        """
        if not portfolio_snapshot or not portfolio_snapshot.holdings:
            self.figure = self._create_empty_chart("No allocation data available")
            return self.figure

        # Extract allocation data
        symbols = []
        values = []
        percentages = []

        total_value = float(portfolio_snapshot.portfolio_value)

        for holding in portfolio_snapshot.holdings:
            symbols.append(holding.symbol)
            value = float(holding.market_value)
            values.append(value)
            percentage = (value / total_value * 100) if total_value > 0 else 0
            percentages.append(percentage)

        # Create pie chart
        fig = go.Figure(data=[
            go.Pie(
                labels=symbols,
                values=values,
                textinfo='label+percent',
                textposition='auto',
                hovertemplate='<b>%{label}</b><br>' +
                             'Value: $%{value:,.2f}<br>' +
                             'Percentage: %{percent}<extra></extra>',
                marker=dict(
                    colors=[self._get_crypto_color(symbol) for symbol in symbols],
                    line=dict(color='#FFFFFF', width=2)
                )
            )
        ])

        # Update layout
        fig.update_layout(
            title=self.config.title or f"Portfolio Allocation - ${total_value:,.2f}",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width,
            showlegend=self.config.show_legend
        )

        self.figure = fig
        return fig

    def _get_crypto_color(self, symbol: str) -> str:
        """Get color for cryptocurrency symbol."""
        crypto_colors = {
            'BTC': '#f7931a',
            'ETH': '#627eea',
            'ADA': '#0033ad',
            'DOT': '#e6007a',
            'LINK': '#375bd2',
            'LTC': '#bfbbbb',
            'XRP': '#23292f',
            'BCH': '#8dc351'
        }
        return crypto_colors.get(symbol, '#1f77b4')

    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title=self.config.title or "Portfolio Allocation",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width
        )
        return fig


class PriceChart(BaseChart):
    """Price chart with candlesticks and technical indicators."""

    def create(self, data: Dict[str, Any]) -> go.Figure:
        """Create price chart.

        Args:
            data: Dictionary containing:
                - historical_prices: List of HistoricalPrice objects
                - symbol: Symbol name
                - indicators: Optional technical indicators

        Returns:
            Plotly figure object
        """
        historical_prices = data.get('historical_prices', [])
        symbol = data.get('symbol', 'Unknown')
        indicators = data.get('indicators', {})

        if not historical_prices:
            self.figure = self._create_empty_chart(f"No price data available for {symbol}")
            return self.figure

        # Sort prices by timestamp
        sorted_prices = sorted(historical_prices, key=lambda x: x.timestamp)

        # Extract price and volume data
        timestamps = [p.timestamp for p in sorted_prices]
        prices = [float(p.price) for p in sorted_prices]
        # Since HistoricalPrice doesn't have OHLC, simulate them from price
        opens = prices  # Use same price for open
        highs = [price * 1.01 for price in prices]  # Simulate 1% high
        lows = [price * 0.99 for price in prices]   # Simulate 1% low
        closes = prices  # Use same price for close
        volumes = [float(p.volume) if p.volume else 0 for p in sorted_prices]

        # Create subplots
        rows = 2 if volumes and any(v > 0 for v in volumes) else 1
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3] if rows == 2 else [1.0],
            subplot_titles=(f'{symbol} Price', 'Volume') if rows == 2 else (f'{symbol} Price',)
        )

        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=timestamps,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name=symbol,
                increasing_line_color='#2ca02c',
                decreasing_line_color='#d62728'
            ),
            row=1, col=1
        )

        # Add technical indicators
        for indicator_name, indicator_values in indicators.items():
            if len(indicator_values) == len(timestamps):
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=indicator_values,
                        mode='lines',
                        name=indicator_name,
                        line=dict(width=1)
                    ),
                    row=1, col=1
                )

        # Add volume bars if available
        if rows == 2 and volumes:
            colors = ['#2ca02c' if closes[i] >= opens[i] else '#d62728'
                     for i in range(len(closes))]

            fig.add_trace(
                go.Bar(
                    x=timestamps,
                    y=volumes,
                    name='Volume',
                    marker_color=colors,
                    showlegend=False
                ),
                row=2, col=1
            )

        # Update layout
        fig.update_layout(
            title=self.config.title or f"{symbol} Price Chart",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width,
            showlegend=self.config.show_legend,
            xaxis_rangeslider_visible=False
        )

        # Update axes
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        if rows == 2:
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            fig.update_xaxes(title_text="Date", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Date", row=1, col=1)

        self.figure = fig
        return fig

    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title=self.config.title or "Price Chart",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width
        )
        return fig


class PerformanceChart(BaseChart):
    """Performance comparison chart."""

    def create(self, performance_data: Dict[str, List[Tuple[datetime, float]]]) -> go.Figure:
        """Create performance comparison chart.

        Args:
            performance_data: Dictionary mapping asset names to (timestamp, return) tuples

        Returns:
            Plotly figure object
        """
        if not performance_data:
            self.figure = self._create_empty_chart("No performance data available")
            return self.figure

        fig = go.Figure()

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

        for i, (asset_name, data_points) in enumerate(performance_data.items()):
            if not data_points:
                continue

            # Sort by timestamp
            sorted_data = sorted(data_points, key=lambda x: x[0])
            timestamps = [point[0] for point in sorted_data]
            returns = [point[1] * 100 for point in sorted_data]  # Convert to percentage

            color = colors[i % len(colors)]

            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=returns,
                    mode='lines',
                    name=asset_name,
                    line=dict(color=color, width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                 'Date: %{x}<br>' +
                                 'Return: %{y:.2f}%<extra></extra>'
                )
            )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        # Update layout
        fig.update_layout(
            title=self.config.title or "Performance Comparison",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width,
            showlegend=self.config.show_legend,
            xaxis_title="Date",
            yaxis_title="Cumulative Return (%)",
            hovermode='x unified'
        )

        self.figure = fig
        return fig

    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title=self.config.title or "Performance Comparison",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width
        )
        return fig


class TechnicalChart(BaseChart):
    """Technical analysis chart with multiple indicators."""

    def create(self, data: Dict[str, Any]) -> go.Figure:
        """Create technical analysis chart.

        Args:
            data: Dictionary containing price data and technical indicators

        Returns:
            Plotly figure object
        """
        # This is a placeholder for advanced technical analysis
        # In a full implementation, this would include RSI, MACD, Bollinger Bands, etc.

        fig = go.Figure()
        fig.add_annotation(
            text="Technical Analysis Chart - Coming Soon",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )

        fig.update_layout(
            title=self.config.title or "Technical Analysis",
            template=self.config.theme,
            height=self.config.height,
            width=self.config.width
        )

        self.figure = fig
        return fig
    
    def create_portfolio_performance_chart(self,
                                         snapshots: List[PortfolioSnapshot],
                                         title: str = "Portfolio Performance") -> go.Figure:
        """Create portfolio performance line chart using new chart system.

        Args:
            snapshots: List of portfolio snapshots over time
            title: Chart title

        Returns:
            Plotly figure object
        """
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title=title,
            height=600,
            theme=self.default_layout['template']
        )
        chart = PortfolioChart(config)
        return chart.create(snapshots)
    
    def create_allocation_pie_chart(self,
                                   portfolio_snapshot: PortfolioSnapshot,
                                   title: str = "Portfolio Allocation") -> go.Figure:
        """Create portfolio allocation pie chart using new chart system.

        Args:
            portfolio_snapshot: Current portfolio snapshot
            title: Chart title

        Returns:
            Plotly figure object
        """
        config = ChartConfig(
            chart_type=ChartType.PIE,
            title=title,
            height=500,
            theme=self.default_layout['template']
        )
        chart = AllocationChart(config)
        return chart.create(portfolio_snapshot)
    
    def create_candlestick_chart(self,
                                historical_prices: List[HistoricalPrice],
                                symbol: str,
                                indicators: Optional[Dict[str, List[float]]] = None) -> go.Figure:
        """Create candlestick chart using new chart system.

        Args:
            historical_prices: Historical price data
            symbol: Cryptocurrency symbol
            indicators: Optional technical indicators to overlay

        Returns:
            Plotly figure object
        """
        config = ChartConfig(
            chart_type=ChartType.CANDLESTICK,
            title=f"{symbol} Price Chart",
            height=700,
            theme=self.default_layout['template']
        )
        chart = PriceChart(config)
        data = {
            'historical_prices': historical_prices,
            'symbol': symbol,
            'indicators': indicators or {}
        }
        return chart.create(data)
    
    def create_performance_comparison_chart(self,
                                          performance_data: Dict[str, List[Tuple[datetime, float]]],
                                          title: str = "Performance Comparison") -> go.Figure:
        """Create performance comparison chart using new chart system.

        Args:
            performance_data: Dict mapping names to (timestamp, return) tuples
            title: Chart title

        Returns:
            Plotly figure object
        """
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title=title,
            height=500,
            theme=self.default_layout['template']
        )
        chart = PerformanceChart(config)
        return chart.create(performance_data)
    
    def create_risk_return_scatter(self, 
                                  risk_return_data: List[Dict[str, Any]],
                                  title: str = "Risk vs Return Analysis") -> go.Figure:
        """Create risk vs return scatter plot.
        
        Args:
            risk_return_data: List of dicts with 'name', 'risk', 'return', 'size' keys
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not risk_return_data:
            return self._create_empty_chart("No risk/return data available")
        
        names = [item['name'] for item in risk_return_data]
        risks = [item['risk'] for item in risk_return_data]
        returns = [item['return'] for item in risk_return_data]
        sizes = [item.get('size', 20) for item in risk_return_data]
        
        fig = go.Figure(data=go.Scatter(
            x=risks,
            y=returns,
            mode='markers+text',
            text=names,
            textposition='top center',
            marker=dict(
                size=sizes,
                color=returns,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Return (%)"),
                line=dict(width=2, color='DarkSlateGrey')
            ),
            hovertemplate='<b>%{text}</b><br>' +
                         'Risk: %{x:.2f}%<br>' +
                         'Return: %{y:.2f}%<extra></extra>'
        ))
        
        # Add quadrant lines
        if risks and returns:
            avg_risk = np.mean(risks)
            avg_return = np.mean(returns)
            
            fig.add_vline(x=avg_risk, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_hline(y=avg_return, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            title=title,
            **self.default_layout,
            height=500,
            xaxis_title="Risk (Volatility %)",
            yaxis_title="Return (%)"
        )
        
        return fig
    
    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message.
        
        Args:
            message: Message to display
            
        Returns:
            Empty Plotly figure with message
        """
        fig = go.Figure()
        
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        
        fig.update_layout(
            **self.default_layout,
            height=400,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        
        return fig
    
    def update_chart_theme(self, theme: str = 'plotly_white') -> None:
        """Update default chart theme.
        
        Args:
            theme: Plotly theme name
        """
        self.default_layout['template'] = theme
        
        if theme == 'plotly_dark':
            self.default_colors.update({
                'background': '#2f2f2f',
                'grid': '#404040'
            })
        else:
            self.default_colors.update({
                'background': '#ffffff',
                'grid': '#e6e6e6'
            })
    
    def get_chart_config(self) -> Dict[str, Any]:
        """Get chart configuration for frontend.
        
        Returns:
            Chart configuration dictionary
        """
        return {
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d'],
            'displaylogo': False,
            'toImageButtonOptions': {
                'format': 'png',
                'filename': 'portfolio_chart',
                'height': 600,
                'width': 800,
                'scale': 2
            }
        }

"""Interactive chart generation using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
import logging

from ..analytics.models import PortfolioSnapshot, PortfolioHolding, PerformanceMetrics
from ..data.models import HistoricalPrice

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Interactive chart generation engine using Plotly."""
    
    def __init__(self):
        """Initialize chart generator."""
        self.default_colors = {
            'primary': '#1f77b4',
            'secondary': '#ff7f0e', 
            'success': '#2ca02c',
            'danger': '#d62728',
            'warning': '#ff7f0e',
            'info': '#17a2b8',
            'background': '#ffffff',
            'grid': '#e6e6e6'
        }
        
        self.default_layout = {
            'template': 'plotly_white',
            'font': {'family': 'Arial, sans-serif', 'size': 12},
            'margin': {'l': 50, 'r': 50, 't': 50, 'b': 50},
            'showlegend': True,
            'hovermode': 'x unified'
        }
    
    def create_portfolio_performance_chart(self, 
                                         snapshots: List[PortfolioSnapshot],
                                         title: str = "Portfolio Performance") -> go.Figure:
        """Create portfolio performance line chart.
        
        Args:
            snapshots: List of portfolio snapshots over time
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not snapshots:
            return self._create_empty_chart("No portfolio data available")
        
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
                line=dict(color=self.default_colors['primary'], width=2),
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
                line=dict(color=self.default_colors['secondary'], width=1, dash='dash'),
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
                line=dict(color=self.default_colors['success'], width=2),
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
            title=title,
            **self.default_layout,
            height=600
        )
        
        # Update y-axes
        fig.update_yaxes(title_text="Value ($)", row=1, col=1)
        fig.update_yaxes(title_text="Return (%)", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        
        return fig
    
    def create_allocation_pie_chart(self, 
                                   portfolio_snapshot: PortfolioSnapshot,
                                   title: str = "Portfolio Allocation") -> go.Figure:
        """Create portfolio allocation pie chart.
        
        Args:
            portfolio_snapshot: Current portfolio snapshot
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not portfolio_snapshot.holdings:
            return self._create_empty_chart("No holdings data available")
        
        # Extract allocation data
        symbols = []
        values = []
        percentages = []
        
        total_value = portfolio_snapshot.total_value
        
        for holding in portfolio_snapshot.holdings:
            if holding.market_value > 0:
                symbols.append(holding.symbol)
                values.append(float(holding.market_value))
                if total_value > 0:
                    percentage = float((holding.market_value / total_value) * 100)
                    percentages.append(percentage)
                else:
                    percentages.append(0)
        
        # Add cash if present
        if portfolio_snapshot.cash_balance > 0:
            symbols.append('CASH')
            values.append(float(portfolio_snapshot.cash_balance))
            if total_value > 0:
                cash_percentage = float((portfolio_snapshot.cash_balance / portfolio_snapshot.portfolio_value) * 100)
                percentages.append(cash_percentage)
            else:
                percentages.append(0)
        
        if not symbols:
            return self._create_empty_chart("No allocation data available")
        
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
                    colors=px.colors.qualitative.Set3[:len(symbols)],
                    line=dict(color='#FFFFFF', width=2)
                )
            )
        ])
        
        fig.update_layout(
            title=title,
            **self.default_layout,
            height=500
        )
        
        return fig
    
    def create_candlestick_chart(self, 
                                historical_prices: List[HistoricalPrice],
                                symbol: str,
                                indicators: Optional[Dict[str, List[float]]] = None) -> go.Figure:
        """Create candlestick chart with optional technical indicators.
        
        Args:
            historical_prices: Historical price data
            symbol: Cryptocurrency symbol
            indicators: Optional technical indicators to overlay
            
        Returns:
            Plotly figure object
        """
        if not historical_prices:
            return self._create_empty_chart(f"No price data available for {symbol}")
        
        # Sort by timestamp
        sorted_prices = sorted(historical_prices, key=lambda x: x.timestamp)
        
        # Extract price and volume data
        timestamps = [p.timestamp for p in sorted_prices]
        # Since HistoricalPrice doesn't have OHLC, use price for all OHLC values
        prices = [float(p.price) for p in sorted_prices]
        opens = prices  # Use same price for open
        highs = [price * 1.02 for price in prices]  # Simulate 2% high
        lows = [price * 0.98 for price in prices]   # Simulate 2% low
        closes = prices  # Use same price for close
        volumes = [float(p.volume) if p.volume else 0 for p in sorted_prices]
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=(f'{symbol} Price', 'Volume'),
            vertical_spacing=0.1,
            row_heights=[0.8, 0.2],
            shared_xaxes=True
        )
        
        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=timestamps,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name=symbol,
                increasing_line_color=self.default_colors['success'],
                decreasing_line_color=self.default_colors['danger']
            ),
            row=1, col=1
        )
        
        # Add technical indicators if provided
        if indicators:
            for indicator_name, indicator_values in indicators.items():
                if len(indicator_values) == len(timestamps):
                    fig.add_trace(
                        go.Scatter(
                            x=timestamps,
                            y=indicator_values,
                            mode='lines',
                            name=indicator_name,
                            line=dict(width=1),
                            opacity=0.8
                        ),
                        row=1, col=1
                    )
        
        # Volume bars
        colors = ['red' if closes[i] < opens[i] else 'green' for i in range(len(closes))]
        fig.add_trace(
            go.Bar(
                x=timestamps,
                y=volumes,
                name='Volume',
                marker_color=colors,
                opacity=0.6,
                showlegend=False
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f'{symbol} Price Chart',
            **self.default_layout,
            height=700,
            xaxis_rangeslider_visible=False
        )
        
        # Update axes
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        
        return fig
    
    def create_performance_comparison_chart(self, 
                                          performance_data: Dict[str, List[Tuple[datetime, float]]],
                                          title: str = "Performance Comparison") -> go.Figure:
        """Create performance comparison chart for multiple assets/portfolios.
        
        Args:
            performance_data: Dict mapping names to (timestamp, return) tuples
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        if not performance_data:
            return self._create_empty_chart("No performance data available")
        
        fig = go.Figure()
        
        colors = px.colors.qualitative.Set1
        
        for i, (name, data) in enumerate(performance_data.items()):
            if data:
                timestamps, returns = zip(*data)
                
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=returns,
                        mode='lines',
                        name=name,
                        line=dict(
                            color=colors[i % len(colors)],
                            width=2
                        ),
                        hovertemplate='<b>%{fullData.name}</b><br>' +
                                     'Date: %{x}<br>' +
                                     'Return: %{y:.2f}%<extra></extra>'
                    )
                )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            title=title,
            **self.default_layout,
            height=500,
            yaxis_title="Cumulative Return (%)",
            xaxis_title="Date"
        )
        
        return fig
    
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

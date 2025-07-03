"""ASCII charts for terminal display using Rich."""

import math
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
import logging

from ..analytics.models import PortfolioSnapshot, PortfolioHolding

logger = logging.getLogger(__name__)


class TerminalCharts:
    """ASCII chart generation for terminal display."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize terminal charts.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.chart_chars = {
            'full': '█',
            'seven_eighths': '▉',
            'three_quarters': '▊',
            'five_eighths': '▋',
            'half': '▌',
            'three_eighths': '▍',
            'quarter': '▎',
            'eighth': '▏',
            'empty': ' '
        }
        
        self.colors = {
            'green': 'green',
            'red': 'red',
            'blue': 'blue',
            'yellow': 'yellow',
            'cyan': 'cyan',
            'magenta': 'magenta',
            'white': 'white',
            'bright_green': 'bright_green',
            'bright_red': 'bright_red'
        }
    
    def create_sparkline(self, values: List[float], width: int = 20) -> str:
        """Create a sparkline chart.
        
        Args:
            values: List of numeric values
            width: Width of the sparkline
            
        Returns:
            Sparkline string
        """
        if not values or len(values) < 2:
            return '─' * width
        
        # Normalize values to fit width
        if len(values) > width:
            # Sample values to fit width
            step = len(values) / width
            sampled_values = [values[int(i * step)] for i in range(width)]
        else:
            sampled_values = values
        
        if not sampled_values:
            return '─' * width
        
        min_val = min(sampled_values)
        max_val = max(sampled_values)
        
        if min_val == max_val:
            return '─' * len(sampled_values)
        
        # Map values to sparkline characters
        sparkline_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        
        sparkline = ''
        for value in sampled_values:
            normalized = (value - min_val) / (max_val - min_val)
            char_index = min(int(normalized * len(sparkline_chars)), len(sparkline_chars) - 1)
            sparkline += sparkline_chars[char_index]
        
        return sparkline
    
    def create_horizontal_bar_chart(self, data: Dict[str, float], 
                                   title: str = "Bar Chart",
                                   width: int = 40,
                                   show_values: bool = True) -> Panel:
        """Create horizontal bar chart.
        
        Args:
            data: Dictionary mapping labels to values
            title: Chart title
            width: Chart width
            show_values: Whether to show values
            
        Returns:
            Rich Panel with bar chart
        """
        if not data:
            return Panel("No data available", title=title)
        
        max_value = max(data.values()) if data.values() else 1
        max_label_length = max(len(label) for label in data.keys()) if data.keys() else 0
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan", width=max_label_length)
        table.add_column("Bar", width=width)
        if show_values:
            table.add_column("Value", style="bold", justify="right")
        
        for label, value in data.items():
            # Calculate bar length
            if max_value > 0:
                bar_length = int((value / max_value) * width)
            else:
                bar_length = 0
            
            # Create bar
            bar = '█' * bar_length + '░' * (width - bar_length)
            
            # Color bar based on value
            if value > 0:
                bar_colored = f"[green]{bar}[/green]"
            else:
                bar_colored = f"[red]{bar}[/red]"
            
            # Add row
            if show_values:
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                table.add_row(label, bar_colored, value_str)
            else:
                table.add_row(label, bar_colored)
        
        return Panel(table, title=title, border_style="blue")
    
    def create_line_chart(self, values: List[float], 
                         labels: Optional[List[str]] = None,
                         title: str = "Line Chart",
                         height: int = 10,
                         width: int = 60) -> Panel:
        """Create ASCII line chart.
        
        Args:
            values: List of numeric values
            labels: Optional labels for x-axis
            title: Chart title
            height: Chart height
            width: Chart width
            
        Returns:
            Rich Panel with line chart
        """
        if not values:
            return Panel("No data available", title=title)
        
        if len(values) == 1:
            return Panel(f"Single value: {values[0]}", title=title)
        
        # Normalize values
        min_val = min(values)
        max_val = max(values)
        
        if min_val == max_val:
            # All values are the same
            chart_lines = ['─' * width for _ in range(height)]
        else:
            # Create chart grid
            chart_grid = [[' ' for _ in range(width)] for _ in range(height)]
            
            # Plot points
            for i, value in enumerate(values):
                if i >= width:
                    break
                
                # Normalize value to chart height
                normalized = (value - min_val) / (max_val - min_val)
                y = int((1 - normalized) * (height - 1))  # Invert y-axis
                y = max(0, min(height - 1, y))
                
                chart_grid[y][i] = '●'
                
                # Connect points with lines
                if i > 0:
                    prev_value = values[i - 1]
                    prev_normalized = (prev_value - min_val) / (max_val - min_val)
                    prev_y = int((1 - prev_normalized) * (height - 1))
                    prev_y = max(0, min(height - 1, prev_y))
                    
                    # Draw line between points
                    start_y, end_y = sorted([prev_y, y])
                    for line_y in range(start_y, end_y + 1):
                        if chart_grid[line_y][i - 1] == ' ':
                            chart_grid[line_y][i - 1] = '│'
                        if line_y != y and chart_grid[line_y][i] == ' ':
                            chart_grid[line_y][i] = '│'
            
            # Convert grid to strings
            chart_lines = [''.join(row) for row in chart_grid]
        
        # Add y-axis labels
        y_labels = []
        for i in range(height):
            if height > 1:
                value = max_val - (i / (height - 1)) * (max_val - min_val)
            else:
                value = min_val
            y_labels.append(f"{value:.2f}")
        
        # Create table with y-axis and chart
        table = Table(show_header=False, box=None, padding=(0, 0))
        table.add_column("Y", style="dim", width=8, justify="right")
        table.add_column("Chart", width=width)
        
        for i, line in enumerate(chart_lines):
            table.add_row(y_labels[i], line)
        
        # Add x-axis if labels provided
        if labels and len(labels) >= 2:
            x_axis = ""
            label_width = width // min(len(labels), 5)  # Show max 5 labels
            for i in range(0, min(len(labels), 5)):
                if i * label_width < width:
                    x_axis += labels[i][:label_width].ljust(label_width)
            
            table.add_row("", "─" * width)
            table.add_row("", x_axis[:width])
        
        return Panel(table, title=title, border_style="blue")
    
    def create_portfolio_allocation_chart(self, portfolio_snapshot: PortfolioSnapshot,
                                        title: str = "Portfolio Allocation") -> Panel:
        """Create portfolio allocation chart.
        
        Args:
            portfolio_snapshot: Portfolio snapshot
            title: Chart title
            
        Returns:
            Rich Panel with allocation chart
        """
        if not portfolio_snapshot.holdings:
            return Panel("No holdings data", title=title)
        
        # Calculate allocations
        total_value = portfolio_snapshot.total_value
        allocations = {}
        
        for holding in portfolio_snapshot.holdings:
            if total_value > 0:
                percentage = float((holding.market_value / total_value) * 100)
                allocations[holding.symbol] = percentage
            else:
                allocations[holding.symbol] = 0.0
        
        # Add cash if present
        if portfolio_snapshot.cash_balance > 0:
            portfolio_value = portfolio_snapshot.portfolio_value
            if portfolio_value > 0:
                cash_percentage = float((portfolio_snapshot.cash_balance / portfolio_value) * 100)
                allocations['CASH'] = cash_percentage
        
        return self.create_horizontal_bar_chart(
            allocations, 
            title=title, 
            width=30,
            show_values=True
        )
    
    def create_performance_sparklines(self, performance_data: Dict[str, List[float]],
                                    title: str = "Performance Trends") -> Panel:
        """Create sparklines for multiple performance metrics.
        
        Args:
            performance_data: Dictionary mapping metric names to value lists
            title: Chart title
            
        Returns:
            Rich Panel with sparklines
        """
        if not performance_data:
            return Panel("No performance data", title=title)
        
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("Metric", style="cyan", width=15)
        table.add_column("Trend", width=25)
        table.add_column("Latest", style="bold", justify="right", width=10)
        
        for metric, values in performance_data.items():
            if values:
                sparkline = self.create_sparkline(values, 25)
                latest_value = values[-1]
                
                # Color latest value based on sign
                if latest_value > 0:
                    latest_colored = f"[green]+{latest_value:.2f}%[/green]"
                elif latest_value < 0:
                    latest_colored = f"[red]{latest_value:.2f}%[/red]"
                else:
                    latest_colored = f"{latest_value:.2f}%"
                
                # Color sparkline based on trend
                if len(values) >= 2:
                    if values[-1] > values[0]:
                        sparkline_colored = f"[green]{sparkline}[/green]"
                    elif values[-1] < values[0]:
                        sparkline_colored = f"[red]{sparkline}[/red]"
                    else:
                        sparkline_colored = sparkline
                else:
                    sparkline_colored = sparkline
                
                table.add_row(metric, sparkline_colored, latest_colored)
            else:
                table.add_row(metric, "No data", "N/A")
        
        return Panel(table, title=title, border_style="blue")
    
    def create_summary_dashboard(self, portfolio_snapshot: PortfolioSnapshot,
                               performance_data: Optional[Dict[str, List[float]]] = None) -> None:
        """Create comprehensive dashboard display.
        
        Args:
            portfolio_snapshot: Current portfolio snapshot
            performance_data: Optional performance trend data
        """
        # Portfolio summary
        summary_table = Table(title="Portfolio Summary", box=box.ROUNDED)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="bold")
        
        summary_table.add_row("Total Value", f"${portfolio_snapshot.total_value:,.2f}")
        summary_table.add_row("Total Cost", f"${portfolio_snapshot.total_cost:,.2f}")
        summary_table.add_row("Unrealized P&L", f"${portfolio_snapshot.total_unrealized_pnl:,.2f}")
        
        pnl_pct = portfolio_snapshot.total_unrealized_pnl_percentage
        if pnl_pct > 0:
            pnl_colored = f"[green]+{pnl_pct:.2f}%[/green]"
        elif pnl_pct < 0:
            pnl_colored = f"[red]{pnl_pct:.2f}%[/red]"
        else:
            pnl_colored = f"{pnl_pct:.2f}%"
        
        summary_table.add_row("P&L %", pnl_colored)
        summary_table.add_row("Holdings", str(len(portfolio_snapshot.holdings)))
        
        # Holdings table
        holdings_table = Table(title="Holdings", box=box.ROUNDED)
        holdings_table.add_column("Symbol", style="cyan")
        holdings_table.add_column("Quantity", justify="right")
        holdings_table.add_column("Price", justify="right")
        holdings_table.add_column("Value", justify="right")
        holdings_table.add_column("P&L %", justify="right")
        
        for holding in portfolio_snapshot.holdings:
            pnl_pct = holding.unrealized_pnl_percentage
            if pnl_pct > 0:
                pnl_colored = f"[green]+{pnl_pct:.2f}%[/green]"
            elif pnl_pct < 0:
                pnl_colored = f"[red]{pnl_pct:.2f}%[/red]"
            else:
                pnl_colored = f"{pnl_pct:.2f}%"
            
            holdings_table.add_row(
                holding.symbol,
                f"{holding.quantity:.4f}",
                f"${holding.current_price:,.2f}",
                f"${holding.market_value:,.2f}",
                pnl_colored
            )
        
        # Create layout
        panels = [
            Panel(summary_table, border_style="green"),
            Panel(holdings_table, border_style="blue")
        ]
        
        # Add allocation chart
        allocation_chart = self.create_portfolio_allocation_chart(portfolio_snapshot)
        panels.append(allocation_chart)
        
        # Add performance sparklines if available
        if performance_data:
            sparklines = self.create_performance_sparklines(performance_data)
            panels.append(sparklines)
        
        # Display in columns
        if len(panels) >= 4:
            # 2x2 layout
            top_row = Columns([panels[0], panels[1]], equal=True)
            bottom_row = Columns([panels[2], panels[3]], equal=True)
            self.console.print(top_row)
            self.console.print(bottom_row)
        else:
            # Single row
            columns = Columns(panels, equal=True)
            self.console.print(columns)
    
    def print_chart(self, chart: Panel) -> None:
        """Print chart to console.
        
        Args:
            chart: Rich Panel to print
        """
        self.console.print(chart)
    
    def clear_screen(self) -> None:
        """Clear the console screen."""
        self.console.clear()
    
    def create_price_chart(self, prices: List[float], 
                          timestamps: Optional[List[datetime]] = None,
                          symbol: str = "Price",
                          height: int = 15) -> Panel:
        """Create price chart with timestamps.
        
        Args:
            prices: List of price values
            timestamps: Optional timestamps
            symbol: Symbol name
            height: Chart height
            
        Returns:
            Rich Panel with price chart
        """
        if not prices:
            return Panel("No price data", title=f"{symbol} Price Chart")
        
        # Create labels from timestamps
        labels = None
        if timestamps and len(timestamps) == len(prices):
            # Show only a few timestamp labels
            num_labels = min(5, len(timestamps))
            step = len(timestamps) // num_labels if num_labels > 0 else 1
            labels = [timestamps[i].strftime("%m/%d") for i in range(0, len(timestamps), step)]
        
        return self.create_line_chart(
            prices, 
            labels=labels,
            title=f"{symbol} Price Chart",
            height=height,
            width=60
        )

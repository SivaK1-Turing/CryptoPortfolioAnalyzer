"""CLI commands for visualization and charting."""

import asyncio
import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box

from ..core.context import get_current_context
from ..visualization.charts import ChartGenerator
from ..visualization.terminal_charts import TerminalCharts
from ..visualization.indicators import TechnicalIndicators
from ..visualization.exports import ChartExporter
from ..analytics.portfolio import PortfolioAnalyzer
from ..data.service import get_data_service

console = Console()


def async_command(f):
    """Decorator to make Click commands async-compatible."""
    import functools
    
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.pass_context
def visualize(ctx):
    """Visualization and charting commands."""
    pass


@visualize.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--format', 'output_format', type=click.Choice(['terminal', 'html', 'png', 'svg']), 
              default='terminal', help='Output format')
@click.option('--output-file', '-o', type=click.Path(), 
              help='Output file for chart (not needed for terminal format)')
@click.option('--theme', type=click.Choice(['light', 'dark']), default='light',
              help='Chart theme')
@click.pass_context
@async_command
async def portfolio(ctx, portfolio_file: Optional[str], output_format: str, 
                   output_file: Optional[str], theme: str):
    """Generate portfolio performance chart.
    
    Examples:
        crypto-portfolio visualize portfolio --format terminal
        crypto-portfolio visualize portfolio --format html --output-file portfolio.html
        crypto-portfolio visualize portfolio --format png --output-file portfolio.png
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would generate portfolio chart in {output_format} format[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating portfolio chart...", total=None)
            
            # Create portfolio snapshot
            analyzer = PortfolioAnalyzer()
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_data['holdings'])
            
            if output_format == 'terminal':
                # Terminal ASCII chart
                terminal_charts = TerminalCharts(console)
                
                # Create dashboard
                terminal_charts.create_summary_dashboard(current_snapshot)
                
                # Create allocation chart
                allocation_chart = terminal_charts.create_portfolio_allocation_chart(current_snapshot)
                terminal_charts.print_chart(allocation_chart)
                
            else:
                # Interactive chart
                chart_generator = ChartGenerator()
                if theme == 'dark':
                    chart_generator.update_chart_theme('plotly_dark')
                
                # Create allocation pie chart
                fig = chart_generator.create_allocation_pie_chart(current_snapshot)
                
                if output_format == 'html':
                    if not output_file:
                        output_file = 'portfolio_chart.html'
                    
                    fig.write_html(output_file, include_plotlyjs=True)
                    console.print(f"[green]Chart saved to {output_file}[/green]")
                    
                    # Open in browser
                    if click.confirm("Open chart in browser?"):
                        webbrowser.open(f"file://{Path(output_file).absolute()}")
                
                else:  # png, svg
                    if not output_file:
                        output_file = f'portfolio_chart.{output_format}'
                    
                    exporter = ChartExporter()
                    if exporter.export_chart(fig, output_file, output_format):
                        console.print(f"[green]Chart exported to {output_file}[/green]")
                    else:
                        console.print("[red]Failed to export chart[/red]")
            
            progress.update(task, completed=True)
            
    except Exception as e:
        console.print(f"[red]Error generating portfolio chart: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@visualize.command()
@click.argument('symbol', required=True)
@click.option('--days', type=int, default=30, help='Number of days of price data')
@click.option('--indicators', multiple=True, 
              type=click.Choice(['sma', 'ema', 'rsi', 'macd', 'bollinger']),
              help='Technical indicators to include')
@click.option('--format', 'output_format', type=click.Choice(['terminal', 'html', 'png', 'svg']), 
              default='terminal', help='Output format')
@click.option('--output-file', '-o', type=click.Path(), 
              help='Output file for chart')
@click.option('--theme', type=click.Choice(['light', 'dark']), default='light',
              help='Chart theme')
@click.pass_context
@async_command
async def price(ctx, symbol: str, days: int, indicators: List[str], 
               output_format: str, output_file: Optional[str], theme: str):
    """Generate price chart with technical indicators.
    
    Examples:
        crypto-portfolio visualize price BTC --days 30 --format terminal
        crypto-portfolio visualize price ETH --indicators sma ema rsi --format html
        crypto-portfolio visualize price ADA --days 90 --format png --output-file ada_chart.png
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would generate {symbol} price chart with indicators: {indicators}[/yellow]")
        return
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Fetching {symbol} price data...", total=None)
            
            # Get data service
            data_service = await get_data_service()
            
            # Fetch historical data
            from datetime import datetime, timezone, timedelta
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            historical_prices = await data_service.get_historical_prices(symbol, start_date, end_date)
            
            if not historical_prices:
                console.print(f"[red]No price data available for {symbol}[/red]")
                return
            
            progress.update(task, description="Calculating technical indicators...")
            
            # Calculate technical indicators
            tech_indicators = TechnicalIndicators()
            calculated_indicators = {}
            
            if indicators:
                all_indicators = tech_indicators.calculate_all_indicators(historical_prices)
                
                for indicator in indicators:
                    if indicator == 'sma':
                        calculated_indicators['SMA_20'] = all_indicators.get('SMA_20', [])
                    elif indicator == 'ema':
                        calculated_indicators['EMA_12'] = all_indicators.get('EMA_12', [])
                    elif indicator == 'rsi':
                        calculated_indicators['RSI'] = all_indicators.get('RSI', [])
                    elif indicator == 'macd':
                        calculated_indicators['MACD'] = all_indicators.get('MACD', [])
                        calculated_indicators['MACD_Signal'] = all_indicators.get('MACD_Signal', [])
                    elif indicator == 'bollinger':
                        calculated_indicators['BB_Upper'] = all_indicators.get('BB_Upper', [])
                        calculated_indicators['BB_Lower'] = all_indicators.get('BB_Lower', [])
            
            progress.update(task, description="Generating chart...")
            
            if output_format == 'terminal':
                # Terminal ASCII chart
                terminal_charts = TerminalCharts(console)
                
                # Extract price data
                prices = [float(p.price) for p in historical_prices]
                timestamps = [p.timestamp for p in historical_prices]
                
                # Create price chart
                price_chart = terminal_charts.create_price_chart(prices, timestamps, symbol)
                terminal_charts.print_chart(price_chart)
                
                # Show technical indicator signals if calculated
                if calculated_indicators:
                    signals = tech_indicators.get_indicator_signals(all_indicators)
                    if signals:
                        signals_panel = _create_signals_panel(signals)
                        console.print(signals_panel)
                
            else:
                # Interactive chart
                chart_generator = ChartGenerator()
                if theme == 'dark':
                    chart_generator.update_chart_theme('plotly_dark')
                
                # Create candlestick chart
                fig = chart_generator.create_candlestick_chart(
                    historical_prices, symbol, calculated_indicators
                )
                
                if output_format == 'html':
                    if not output_file:
                        output_file = f'{symbol.lower()}_chart.html'
                    
                    fig.write_html(output_file, include_plotlyjs=True)
                    console.print(f"[green]Chart saved to {output_file}[/green]")
                    
                    # Open in browser
                    if click.confirm("Open chart in browser?"):
                        webbrowser.open(f"file://{Path(output_file).absolute()}")
                
                else:  # png, svg
                    if not output_file:
                        output_file = f'{symbol.lower()}_chart.{output_format}'
                    
                    exporter = ChartExporter()
                    if exporter.export_chart(fig, output_file, output_format):
                        console.print(f"[green]Chart exported to {output_file}[/green]")
                    else:
                        console.print("[red]Failed to export chart[/red]")
            
            progress.update(task, completed=True)
            
    except Exception as e:
        console.print(f"[red]Error generating price chart: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@visualize.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--output-dir', '-o', type=click.Path(), default='chart_gallery',
              help='Output directory for chart gallery')
@click.option('--format', 'output_format', type=click.Choice(['png', 'svg', 'html']), 
              default='png', help='Chart format')
@click.option('--theme', type=click.Choice(['light', 'dark']), default='light',
              help='Chart theme')
@click.pass_context
@async_command
async def gallery(ctx, portfolio_file: Optional[str], output_dir: str, 
                 output_format: str, theme: str):
    """Generate comprehensive chart gallery.
    
    Examples:
        crypto-portfolio visualize gallery --output-dir my_charts
        crypto-portfolio visualize gallery --format svg --theme dark
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would generate chart gallery in {output_dir}[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating chart gallery...", total=None)
            
            # Initialize components
            chart_generator = ChartGenerator()
            if theme == 'dark':
                chart_generator.update_chart_theme('plotly_dark')
            
            analyzer = PortfolioAnalyzer()
            exporter = ChartExporter()
            
            # Create portfolio snapshot
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_data['holdings'])
            
            # Generate charts
            charts = {}
            
            progress.update(task, description="Creating portfolio allocation chart...")
            charts['Portfolio Allocation'] = chart_generator.create_allocation_pie_chart(current_snapshot)
            
            progress.update(task, description="Creating performance chart...")
            # Use current snapshot as single point for demo
            charts['Portfolio Performance'] = chart_generator.create_portfolio_performance_chart([current_snapshot])
            
            # Create price charts for each holding
            data_service = await get_data_service()
            for holding in current_snapshot.holdings:
                progress.update(task, description=f"Creating {holding.symbol} price chart...")
                
                try:
                    from datetime import datetime, timezone, timedelta
                    end_date = datetime.now(timezone.utc)
                    start_date = end_date - timedelta(days=30)
                    
                    historical_prices = await data_service.get_historical_prices(
                        holding.symbol, start_date, end_date
                    )
                    
                    if historical_prices:
                        charts[f'{holding.symbol} Price Chart'] = chart_generator.create_candlestick_chart(
                            historical_prices, holding.symbol
                        )
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not create chart for {holding.symbol}: {e}[/yellow]")
            
            progress.update(task, description="Exporting charts...")
            
            # Export gallery
            gallery_paths = exporter.create_chart_gallery(charts, output_dir, output_format)
            
            progress.update(task, completed=True)
            
            console.print(f"[green]Chart gallery created in {output_dir}[/green]")
            console.print(f"[green]Generated {len(gallery_paths)} charts[/green]")
            
            # Open gallery if HTML format
            if output_format == 'png':
                index_path = Path(output_dir) / "index.html"
                if index_path.exists() and click.confirm("Open gallery in browser?"):
                    webbrowser.open(f"file://{index_path.absolute()}")
            
    except Exception as e:
        console.print(f"[red]Error generating chart gallery: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@visualize.command()
@click.option('--host', default='localhost', help='Dashboard host')
@click.option('--port', type=int, default=8080, help='Dashboard port')
@click.option('--theme', type=click.Choice(['light', 'dark']), default='light', help='Dashboard theme')
@click.option('--auto-refresh', is_flag=True, default=True, help='Enable auto-refresh')
@click.option('--refresh-interval', type=int, default=5, help='Refresh interval in seconds')
@click.pass_context
@async_command
async def dashboard(ctx, host: str, port: int, theme: str, auto_refresh: bool, refresh_interval: int):
    """Launch interactive web dashboard.

    Examples:
        crypto-portfolio visualize dashboard
        crypto-portfolio visualize dashboard --port 8080 --theme dark
        crypto-portfolio visualize dashboard --host 0.0.0.0 --port 3000
    """
    app_ctx = get_current_context()

    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would launch web dashboard on {host}:{port}[/yellow]")
        return

    try:
        from ..visualization.dashboard import WebDashboard, DashboardConfig

        console.print(f"[blue]Starting web dashboard on {host}:{port}...[/blue]")

        # Create dashboard configuration
        config = DashboardConfig(
            host=host,
            port=port,
            title="Crypto Portfolio Dashboard",
            theme=theme,
            auto_refresh=auto_refresh,
            refresh_interval=refresh_interval
        )

        # Create and start dashboard
        dashboard = WebDashboard(config)

        console.print(f"[green]Dashboard starting at http://{host}:{port}[/green]")
        console.print("[yellow]Press Ctrl+C to stop the dashboard[/yellow]")

        # Open browser
        if click.confirm("Open dashboard in browser?"):
            webbrowser.open(f"http://{host}:{port}")

        # Start dashboard (this will block)
        await dashboard.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error launching dashboard: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


def _load_portfolio_data(portfolio_file: Optional[str]) -> Optional[Dict]:
    """Load portfolio data from file or return sample data."""
    if portfolio_file:
        try:
            with open(portfolio_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[red]Error loading portfolio file: {e}[/red]")
            return None
    else:
        # Return sample portfolio data for demo
        return {
            'holdings': [
                {'symbol': 'BTC', 'quantity': 0.5, 'average_cost': 45000},
                {'symbol': 'ETH', 'quantity': 2.0, 'average_cost': 3000},
                {'symbol': 'ADA', 'quantity': 1000, 'average_cost': 1.2}
            ],
            'cash_balance': 5000
        }


def _create_signals_panel(signals: Dict[str, str]) -> Panel:
    """Create panel showing technical indicator signals."""
    from rich.table import Table
    
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Indicator", style="cyan")
    table.add_column("Signal", style="bold")
    
    signal_colors = {
        'BULLISH': 'green',
        'BEARISH': 'red',
        'OVERBOUGHT': 'yellow',
        'OVERSOLD': 'blue',
        'NEUTRAL': 'white'
    }
    
    for indicator, signal in signals.items():
        color = signal_colors.get(signal.split('_')[0], 'white')
        colored_signal = f"[{color}]{signal}[/{color}]"
        table.add_row(indicator, colored_signal)
    
    return Panel(table, title="Technical Signals", border_style="blue")


@visualize.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True),
              help='JSON file with portfolio holdings')
@click.option('--type', 'report_type',
              type=click.Choice(['portfolio_summary', 'performance_analysis', 'risk_assessment', 'allocation_report']),
              default='portfolio_summary', help='Report type')
@click.option('--format', 'output_format', type=click.Choice(['html', 'pdf', 'json']),
              default='html', help='Report format')
@click.option('--output-file', '-o', type=click.Path(),
              help='Output file for report')
@click.option('--theme', type=click.Choice(['light', 'dark']), default='light',
              help='Report theme')
@click.option('--include-charts/--no-charts', default=True, help='Include charts in report')
@click.option('--include-tables/--no-tables', default=True, help='Include tables in report')
@click.pass_context
@async_command
async def report(ctx, portfolio_file: Optional[str], report_type: str, output_format: str,
                output_file: Optional[str], theme: str, include_charts: bool, include_tables: bool):
    """Generate comprehensive portfolio reports.

    Examples:
        crypto-portfolio visualize report --type portfolio_summary --format html
        crypto-portfolio visualize report --type performance_analysis --format pdf
        crypto-portfolio visualize report --format json --output-file report.json
    """
    app_ctx = get_current_context()

    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would generate {report_type} report in {output_format} format[/yellow]")
        return

    try:
        from ..visualization.reports import ReportGenerator, ReportConfig, ReportType, ReportFormat

        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating report...", total=None)

            # Create portfolio snapshots
            analyzer = PortfolioAnalyzer()
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_data['holdings'])

            # Create report configuration
            config = ReportConfig(
                report_type=ReportType(report_type),
                format=ReportFormat(output_format),
                title=f"{report_type.replace('_', ' ').title()} Report",
                include_charts=include_charts,
                include_tables=include_tables,
                theme=theme,
                output_path=output_file
            )

            progress.update(task, description="Generating charts and tables...")

            # Generate report
            generator = ReportGenerator()
            report_path = generator.generate_report(config, [current_snapshot])

            progress.update(task, completed=True)

            console.print(f"[green]Report generated: {report_path}[/green]")

            # Open report if HTML
            if output_format == 'html' and click.confirm("Open report in browser?"):
                webbrowser.open(f"file://{Path(report_path).absolute()}")

    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@visualize.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True),
              help='JSON file with portfolio holdings')
@click.option('--format', 'export_format', type=click.Choice(['csv', 'json', 'excel']),
              default='csv', help='Export format')
@click.option('--output-file', '-o', type=click.Path(),
              help='Output file for export')
@click.option('--include-metadata/--no-metadata', default=True, help='Include metadata in export')
@click.option('--decimal-places', type=int, default=6, help='Number of decimal places')
@click.pass_context
@async_command
async def export(ctx, portfolio_file: Optional[str], export_format: str, output_file: Optional[str],
                include_metadata: bool, decimal_places: int):
    """Export portfolio data to various formats.

    Examples:
        crypto-portfolio visualize export --format csv
        crypto-portfolio visualize export --format excel --output-file portfolio.xlsx
        crypto-portfolio visualize export --format json --include-metadata
    """
    app_ctx = get_current_context()

    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would export portfolio data in {export_format} format[/yellow]")
        return

    try:
        from ..visualization.export import DataExporter, ExportConfig, ExportFormat

        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Exporting data...", total=None)

            # Create portfolio snapshots
            analyzer = PortfolioAnalyzer()
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_data['holdings'])

            # Create export configuration
            config = ExportConfig(
                format=ExportFormat(export_format),
                include_metadata=include_metadata,
                decimal_places=decimal_places,
                output_path=output_file
            )

            # Generate filename if not provided
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"portfolio_export_{timestamp}.{export_format}"

            progress.update(task, description="Processing portfolio data...")

            # Export data
            exporter = DataExporter()
            export_path = exporter.export_data([current_snapshot], config, output_file)

            progress.update(task, completed=True)

            console.print(f"[green]Data exported: {export_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error exporting data: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()

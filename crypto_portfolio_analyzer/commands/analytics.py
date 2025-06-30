"""CLI commands for portfolio analytics and reporting."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box
from decimal import Decimal

from ..core.context import get_current_context
from ..analytics.portfolio import PortfolioAnalyzer
from ..analytics.risk import RiskAnalyzer
from ..analytics.allocation import AllocationAnalyzer
from ..analytics.benchmarks import BenchmarkAnalyzer
from ..analytics.models import PerformancePeriod, PortfolioHolding

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
def analytics(ctx):
    """Portfolio analytics and reporting commands."""
    pass


@analytics.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), 
              default='table', help='Output format')
@click.pass_context
@async_command
async def performance(ctx, portfolio_file: Optional[str], output_format: str):
    """Analyze portfolio performance metrics.
    
    Examples:
        crypto-portfolio analytics performance --portfolio-file my_portfolio.json
        crypto-portfolio analytics performance --format json
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would analyze portfolio performance[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided. Use --portfolio-file or configure default portfolio.[/red]")
            return
        
        analyzer = PortfolioAnalyzer()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing portfolio performance...", total=None)
            
            # Create current snapshot
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_data['holdings'])
            
            # Calculate performance for different periods
            periods = [PerformancePeriod.DAY_1, PerformancePeriod.DAYS_7, 
                      PerformancePeriod.DAYS_30, PerformancePeriod.DAYS_90]
            
            performance_metrics = {}
            historical_snapshots = []  # In real implementation, load from database
            
            for period in periods:
                metrics = await analyzer.calculate_performance_metrics(
                    current_snapshot, historical_snapshots, period
                )
                performance_metrics[period] = metrics
            
            progress.update(task, completed=True)
        
        # Display results
        if output_format == 'table':
            _display_performance_table(current_snapshot, performance_metrics)
        else:
            _display_performance_json(current_snapshot, performance_metrics)
            
    except Exception as e:
        console.print(f"[red]Error analyzing performance: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@analytics.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), 
              default='table', help='Output format')
@click.pass_context
@async_command
async def risk(ctx, portfolio_file: Optional[str], output_format: str):
    """Analyze portfolio risk metrics.
    
    Examples:
        crypto-portfolio analytics risk --portfolio-file my_portfolio.json
        crypto-portfolio analytics risk --format json
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would analyze portfolio risk[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return
        
        risk_analyzer = RiskAnalyzer()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Calculating risk metrics...", total=None)
            
            # In real implementation, load historical snapshots from database
            historical_snapshots = []
            
            risk_metrics = await risk_analyzer.calculate_risk_metrics(historical_snapshots)
            
            progress.update(task, completed=True)
        
        # Display results
        if output_format == 'table':
            _display_risk_table(risk_metrics)
        else:
            _display_risk_json(risk_metrics)
            
    except Exception as e:
        console.print(f"[red]Error analyzing risk: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@analytics.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--target-file', '-t', type=click.Path(exists=True), 
              help='JSON file with target allocations')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), 
              default='table', help='Output format')
@click.pass_context
@async_command
async def allocation(ctx, portfolio_file: Optional[str], target_file: Optional[str], output_format: str):
    """Analyze asset allocation and diversification.
    
    Examples:
        crypto-portfolio analytics allocation --portfolio-file my_portfolio.json
        crypto-portfolio analytics allocation --target-file target_allocation.json
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would analyze asset allocation[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return
        
        # Load target allocations if provided
        target_allocations = None
        if target_file:
            target_allocations = _load_target_allocations(target_file)
        
        portfolio_analyzer = PortfolioAnalyzer()
        allocation_analyzer = AllocationAnalyzer()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing asset allocation...", total=None)
            
            # Create current snapshot
            current_snapshot = await portfolio_analyzer.create_portfolio_snapshot(portfolio_data['holdings'])
            
            # Analyze allocation
            allocation_metrics = allocation_analyzer.analyze_allocation(
                current_snapshot, target_allocations
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if output_format == 'table':
            _display_allocation_table(allocation_metrics)
        else:
            _display_allocation_json(allocation_metrics)
            
    except Exception as e:
        console.print(f"[red]Error analyzing allocation: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@analytics.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--benchmark', '-b', default='BTC', 
              help='Benchmark symbol (BTC, ETH, TOTAL_MARKET)')
@click.option('--period', type=int, default=90, 
              help='Analysis period in days')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), 
              default='table', help='Output format')
@click.pass_context
@async_command
async def benchmark(ctx, portfolio_file: Optional[str], benchmark: str, period: int, output_format: str):
    """Compare portfolio performance to benchmarks.
    
    Examples:
        crypto-portfolio analytics benchmark --benchmark BTC --period 90
        crypto-portfolio analytics benchmark --benchmark ETH --period 30
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would compare portfolio to {benchmark} benchmark[/yellow]")
        return
    
    try:
        # Load portfolio data
        portfolio_data = _load_portfolio_data(portfolio_file)
        if not portfolio_data:
            console.print("[red]No portfolio data provided.[/red]")
            return
        
        benchmark_analyzer = BenchmarkAnalyzer()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Comparing to {benchmark} benchmark...", total=None)
            
            # In real implementation, load historical snapshots from database
            historical_snapshots = []
            
            comparison = await benchmark_analyzer.compare_to_benchmark(
                historical_snapshots, benchmark, period
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if output_format == 'table':
            _display_benchmark_table(comparison)
        else:
            _display_benchmark_json(comparison)
            
    except Exception as e:
        console.print(f"[red]Error comparing to benchmark: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@analytics.command()
@click.option('--portfolio-file', '-p', type=click.Path(exists=True), 
              help='JSON file with portfolio holdings')
@click.option('--output-file', '-o', type=click.Path(), 
              help='Output file for the report')
@click.option('--format', 'output_format', type=click.Choice(['json', 'pdf']), 
              default='json', help='Report format')
@click.pass_context
@async_command
async def report(ctx, portfolio_file: Optional[str], output_file: Optional[str], output_format: str):
    """Generate comprehensive portfolio analytics report.
    
    Examples:
        crypto-portfolio analytics report --output-file report.json
        crypto-portfolio analytics report --format pdf --output-file report.pdf
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would generate comprehensive analytics report[/yellow]")
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
            task = progress.add_task("Generating comprehensive report...", total=None)
            
            # Initialize analyzers
            portfolio_analyzer = PortfolioAnalyzer()
            risk_analyzer = RiskAnalyzer()
            allocation_analyzer = AllocationAnalyzer()
            benchmark_analyzer = BenchmarkAnalyzer()
            
            # Create current snapshot
            current_snapshot = await portfolio_analyzer.create_portfolio_snapshot(portfolio_data['holdings'])
            
            # Calculate all metrics (simplified for demo)
            historical_snapshots = []  # Load from database in real implementation
            
            # Performance metrics
            performance_metrics = {}
            for period in [PerformancePeriod.DAYS_7, PerformancePeriod.DAYS_30, PerformancePeriod.DAYS_90]:
                metrics = await portfolio_analyzer.calculate_performance_metrics(
                    current_snapshot, historical_snapshots, period
                )
                performance_metrics[period] = metrics
            
            # Risk metrics
            risk_metrics = await risk_analyzer.calculate_risk_metrics(historical_snapshots)
            
            # Allocation metrics
            allocation_metrics = allocation_analyzer.analyze_allocation(current_snapshot)
            
            # Benchmark comparisons
            benchmark_comparisons = await benchmark_analyzer.compare_to_multiple_benchmarks(
                historical_snapshots, ['BTC', 'ETH'], 90
            )
            
            progress.update(task, completed=True)
        
        # Generate report
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'portfolio_summary': {
                'total_value': float(current_snapshot.total_value),
                'total_cost': float(current_snapshot.total_cost),
                'unrealized_pnl': float(current_snapshot.total_unrealized_pnl),
                'unrealized_pnl_percentage': current_snapshot.total_unrealized_pnl_percentage,
                'holdings_count': len(current_snapshot.holdings)
            },
            'performance_metrics': {
                period.value: {
                    'total_return_percentage': metrics.total_return_percentage,
                    'annualized_return': metrics.annualized_return,
                    'volatility': metrics.volatility,
                    'sharpe_ratio': metrics.sharpe_ratio
                } for period, metrics in performance_metrics.items()
            },
            'risk_metrics': risk_metrics.to_dict(),
            'allocation_metrics': allocation_metrics.to_dict(),
            'benchmark_comparisons': [
                {
                    'benchmark_name': comp.benchmark_name,
                    'outperformance': comp.outperformance,
                    'alpha': comp.alpha,
                    'beta': comp.beta
                } for comp in benchmark_comparisons
            ]
        }
        
        # Save or display report
        if output_file:
            if output_format == 'json':
                with open(output_file, 'w') as f:
                    json.dump(report_data, f, indent=2)
                console.print(f"[green]Report saved to {output_file}[/green]")
            else:  # PDF
                console.print("[yellow]PDF report generation not yet implemented[/yellow]")
        else:
            console.print(json.dumps(report_data, indent=2))
            
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
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


def _load_target_allocations(target_file: str) -> Optional[Dict[str, float]]:
    """Load target allocations from file."""
    try:
        with open(target_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[red]Error loading target allocations: {e}[/red]")
        return None


def _display_performance_table(snapshot, performance_metrics):
    """Display performance metrics in table format."""
    # Portfolio summary
    summary_table = Table(title="Portfolio Summary", box=box.ROUNDED)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total Value", f"${snapshot.total_value:,.2f}")
    summary_table.add_row("Total Cost", f"${snapshot.total_cost:,.2f}")
    summary_table.add_row("Unrealized P&L", f"${snapshot.total_unrealized_pnl:,.2f}")
    summary_table.add_row("Unrealized P&L %", f"{snapshot.total_unrealized_pnl_percentage:.2f}%")
    summary_table.add_row("Holdings Count", str(len(snapshot.holdings)))
    
    console.print(summary_table)
    
    # Performance metrics
    perf_table = Table(title="Performance Metrics", box=box.ROUNDED)
    perf_table.add_column("Period", style="cyan")
    perf_table.add_column("Total Return", style="green")
    perf_table.add_column("Annualized Return", style="green")
    perf_table.add_column("Volatility", style="yellow")
    perf_table.add_column("Sharpe Ratio", style="blue")
    
    for period, metrics in performance_metrics.items():
        perf_table.add_row(
            period.value,
            f"{metrics.total_return_percentage:.2f}%",
            f"{metrics.annualized_return:.2f}%",
            f"{metrics.volatility:.2f}%",
            f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio else "N/A"
        )
    
    console.print(perf_table)


def _display_performance_json(snapshot, performance_metrics):
    """Display performance metrics in JSON format."""
    data = {
        'portfolio_summary': {
            'total_value': float(snapshot.total_value),
            'total_cost': float(snapshot.total_cost),
            'unrealized_pnl': float(snapshot.total_unrealized_pnl),
            'unrealized_pnl_percentage': snapshot.total_unrealized_pnl_percentage
        },
        'performance_metrics': {
            period.value: {
                'total_return_percentage': metrics.total_return_percentage,
                'annualized_return': metrics.annualized_return,
                'volatility': metrics.volatility,
                'sharpe_ratio': metrics.sharpe_ratio
            } for period, metrics in performance_metrics.items()
        }
    }
    console.print(json.dumps(data, indent=2))


def _display_risk_table(risk_metrics):
    """Display risk metrics in table format."""
    table = Table(title="Risk Metrics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Daily Volatility", f"{risk_metrics.volatility_daily:.4f}")
    table.add_row("Annualized Volatility", f"{risk_metrics.volatility_annualized:.2f}%")
    table.add_row("VaR 95% (Daily)", f"{risk_metrics.var_95_daily:.4f}")
    table.add_row("VaR 99% (Daily)", f"{risk_metrics.var_99_daily:.4f}")
    table.add_row("Sharpe Ratio", f"{risk_metrics.sharpe_ratio:.2f}")
    table.add_row("Sortino Ratio", f"{risk_metrics.sortino_ratio:.2f}")
    table.add_row("Max Drawdown", f"{risk_metrics.max_drawdown:.2f}%")
    
    console.print(table)


def _display_risk_json(risk_metrics):
    """Display risk metrics in JSON format."""
    console.print(json.dumps(risk_metrics.to_dict(), indent=2))


def _display_allocation_table(allocation_metrics):
    """Display allocation metrics in table format."""
    # Current allocations
    alloc_table = Table(title="Current Asset Allocation", box=box.ROUNDED)
    alloc_table.add_column("Asset", style="cyan")
    alloc_table.add_column("Allocation %", style="green")
    
    for symbol, allocation in allocation_metrics.allocations.items():
        alloc_table.add_row(symbol, f"{allocation:.2f}%")
    
    console.print(alloc_table)
    
    # Diversification metrics
    div_table = Table(title="Diversification Metrics", box=box.ROUNDED)
    div_table.add_column("Metric", style="cyan")
    div_table.add_column("Value", style="yellow")
    
    div_table.add_row("Concentration Risk", f"{allocation_metrics.concentration_risk:.2f}")
    div_table.add_row("Diversification Ratio", f"{allocation_metrics.diversification_ratio:.2f}")
    div_table.add_row("Effective Assets", f"{allocation_metrics.effective_assets:.2f}")
    div_table.add_row("Largest Position", f"{allocation_metrics.largest_position:.2f}%")
    
    console.print(div_table)


def _display_allocation_json(allocation_metrics):
    """Display allocation metrics in JSON format."""
    console.print(json.dumps(allocation_metrics.to_dict(), indent=2))


def _display_benchmark_table(comparison):
    """Display benchmark comparison in table format."""
    table = Table(title=f"Benchmark Comparison: {comparison.benchmark_name}", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Portfolio Return", f"{comparison.portfolio_return:.2f}%")
    table.add_row("Benchmark Return", f"{comparison.benchmark_return:.2f}%")
    table.add_row("Outperformance", f"{comparison.outperformance:.2f}%")
    table.add_row("Alpha", f"{comparison.alpha:.2f}%")
    table.add_row("Beta", f"{comparison.beta:.2f}")
    table.add_row("Correlation", f"{comparison.correlation:.2f}")
    table.add_row("Up Capture", f"{comparison.up_capture:.2f}%")
    table.add_row("Down Capture", f"{comparison.down_capture:.2f}%")
    
    console.print(table)


def _display_benchmark_json(comparison):
    """Display benchmark comparison in JSON format."""
    data = {
        'benchmark_name': comparison.benchmark_name,
        'portfolio_return': comparison.portfolio_return,
        'benchmark_return': comparison.benchmark_return,
        'outperformance': comparison.outperformance,
        'alpha': comparison.alpha,
        'beta': comparison.beta,
        'correlation': comparison.correlation,
        'up_capture': comparison.up_capture,
        'down_capture': comparison.down_capture
    }
    console.print(json.dumps(data, indent=2))

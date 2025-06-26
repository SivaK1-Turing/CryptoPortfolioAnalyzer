"""
Portfolio management commands.

This module provides commands for managing cryptocurrency portfolios including
adding/removing holdings, viewing portfolio status, and basic analytics.
"""

import click
from rich.console import Console
from rich.table import Table

from crypto_portfolio_analyzer.core.cli_base import ContextAwareGroup, ContextAwareCommand
from crypto_portfolio_analyzer.core.context import get_current_context

console = Console()


@click.group(cls=ContextAwareGroup, name='portfolio')
def portfolio_group() -> None:
    """Portfolio management commands."""
    pass


@portfolio_group.command(cls=ContextAwareCommand, name='status')
def portfolio_status() -> None:
    """Show portfolio status and summary."""
    app_ctx = get_current_context()
    
    console.print("[bold]Portfolio Status[/bold]")
    console.print()
    
    # Create a sample table for demonstration
    table = Table(title="Current Holdings")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Amount", style="magenta")
    table.add_column("Value (USD)", style="green")
    table.add_column("24h Change", style="yellow")
    
    # Sample data - in real implementation this would come from the portfolio manager
    sample_holdings = [
        ("BTC", "0.5", "$15,000", "+2.5%"),
        ("ETH", "2.0", "$3,200", "-1.2%"),
        ("ADA", "1000", "$450", "+5.8%"),
    ]
    
    for symbol, amount, value, change in sample_holdings:
        table.add_row(symbol, amount, value, change)
    
    console.print(table)
    console.print()
    console.print(f"[bold]Total Portfolio Value:[/bold] [green]$18,650[/green]")
    console.print(f"[bold]24h Change:[/bold] [green]+$320 (+1.75%)[/green]")


@portfolio_group.command(cls=ContextAwareCommand, name='add')
@click.argument('symbol')
@click.argument('amount', type=float)
@click.option('--price', type=float, help='Purchase price (if not current market price)')
@click.option('--date', help='Purchase date (YYYY-MM-DD)')
def add_holding(symbol: str, amount: float, price: float = None, date: str = None) -> None:
    """Add a new holding to the portfolio."""
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would add {amount} {symbol.upper()}")
        if price:
            console.print(f"[yellow]DRY RUN:[/yellow] At price ${price}")
        if date:
            console.print(f"[yellow]DRY RUN:[/yellow] With date {date}")
        return
    
    # In real implementation, this would interact with the portfolio manager
    console.print(f"[green]✓[/green] Added {amount} {symbol.upper()} to portfolio")
    
    if price:
        console.print(f"  Purchase price: ${price}")
    if date:
        console.print(f"  Purchase date: {date}")


@portfolio_group.command(cls=ContextAwareCommand, name='remove')
@click.argument('symbol')
@click.argument('amount', type=float)
def remove_holding(symbol: str, amount: float) -> None:
    """Remove a holding from the portfolio."""
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would remove {amount} {symbol.upper()}")
        return
    
    # In real implementation, this would interact with the portfolio manager
    console.print(f"[green]✓[/green] Removed {amount} {symbol.upper()} from portfolio")


@portfolio_group.command(cls=ContextAwareCommand, name='list')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'csv']), 
              default='table', help='Output format')
def list_holdings(output_format: str) -> None:
    """List all holdings in the portfolio."""
    app_ctx = get_current_context()
    
    # Sample holdings data
    holdings = [
        {"symbol": "BTC", "amount": 0.5, "value": 15000, "change_24h": 2.5},
        {"symbol": "ETH", "amount": 2.0, "value": 3200, "change_24h": -1.2},
        {"symbol": "ADA", "amount": 1000, "value": 450, "change_24h": 5.8},
    ]
    
    if output_format == 'table':
        table = Table(title="Portfolio Holdings")
        table.add_column("Symbol", style="cyan")
        table.add_column("Amount", style="magenta")
        table.add_column("Value (USD)", style="green")
        table.add_column("24h Change (%)", style="yellow")
        
        for holding in holdings:
            change_color = "green" if holding["change_24h"] >= 0 else "red"
            change_sign = "+" if holding["change_24h"] >= 0 else ""
            
            table.add_row(
                holding["symbol"],
                str(holding["amount"]),
                f"${holding['value']:,}",
                f"[{change_color}]{change_sign}{holding['change_24h']:.1f}%[/{change_color}]"
            )
        
        console.print(table)
    
    elif output_format == 'json':
        import json
        console.print(json.dumps(holdings, indent=2))
    
    elif output_format == 'csv':
        console.print("symbol,amount,value,change_24h")
        for holding in holdings:
            console.print(f"{holding['symbol']},{holding['amount']},{holding['value']},{holding['change_24h']}")


# Register the portfolio group with the main CLI
# This would typically be done through entry points in pyproject.toml

"""CLI commands for cryptocurrency data operations."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from ..core.context import get_current_context
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
def data(ctx):
    """Cryptocurrency data fetching and management commands."""
    pass


@data.command()
@click.argument('symbols', nargs=-1, required=True)
@click.option('--currency', '-c', default='usd', help='Target currency (default: usd)')
@click.option('--no-cache', is_flag=True, help='Skip cache and fetch fresh data')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'csv']),
              default='table', help='Output format')
@click.pass_context
@async_command
async def price(ctx, symbols: tuple, currency: str, no_cache: bool, output_format: str):
    """Get current prices for cryptocurrencies.
    
    Examples:
        crypto-portfolio data price BTC ETH
        crypto-portfolio data price BTC --currency eur
        crypto-portfolio data price BTC ETH ADA --format json
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would fetch prices for {', '.join(symbols)}[/yellow]")
        return
    
    try:
        data_service = await get_data_service()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Fetching prices for {len(symbols)} symbols...", total=None)
            
            prices = await data_service.get_multiple_prices(
                list(symbols), 
                currency=currency, 
                use_cache=not no_cache
            )
            
            progress.update(task, completed=True)
        
        if not prices:
            console.print("[red]No price data found for the specified symbols[/red]")
            return
        
        # Display results
        if output_format == 'table':
            _display_prices_table(prices, currency)
        elif output_format == 'json':
            _display_prices_json(prices)
        elif output_format == 'csv':
            _display_prices_csv(prices)
            
    except Exception as e:
        console.print(f"[red]Error fetching prices: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@data.command()
@click.argument('symbol')
@click.option('--days', '-d', type=int, default=30, help='Number of days of historical data')
@click.option('--start-date', type=click.DateTime(['%Y-%m-%d']), help='Start date (YYYY-MM-DD)')
@click.option('--end-date', type=click.DateTime(['%Y-%m-%d']), help='End date (YYYY-MM-DD)')
@click.option('--currency', '-c', default='usd', help='Target currency (default: usd)')
@click.option('--no-cache', is_flag=True, help='Skip cache and fetch fresh data')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'csv']),
              default='table', help='Output format')
@click.pass_context
@async_command
async def historical(ctx, symbol: str, days: int, start_date: Optional[datetime],
                    end_date: Optional[datetime], currency: str, no_cache: bool, output_format: str):
    """Get historical price data for a cryptocurrency.
    
    Examples:
        crypto-portfolio data historical BTC --days 7
        crypto-portfolio data historical ETH --start-date 2024-01-01 --end-date 2024-01-31
        crypto-portfolio data historical BTC --days 30 --format json
    """
    app_ctx = get_current_context()
    
    # Calculate date range
    if start_date and end_date:
        if start_date >= end_date:
            console.print("[red]Start date must be before end date[/red]")
            return
    elif start_date:
        end_date = datetime.now()
    elif end_date:
        start_date = end_date - timedelta(days=days)
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
    
    if app_ctx.dry_run:
        console.print(f"[yellow]DRY RUN: Would fetch historical data for {symbol} from {start_date.date()} to {end_date.date()}[/yellow]")
        return
    
    try:
        data_service = await get_data_service()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Fetching historical data for {symbol}...", total=None)
            
            historical_prices = await data_service.get_historical_prices(
                symbol, 
                start_date, 
                end_date, 
                currency=currency, 
                use_cache=not no_cache
            )
            
            progress.update(task, completed=True)
        
        if not historical_prices:
            console.print(f"[red]No historical data found for {symbol}[/red]")
            return
        
        # Display results
        if output_format == 'table':
            _display_historical_table(historical_prices, symbol, currency)
        elif output_format == 'json':
            _display_historical_json(historical_prices)
        elif output_format == 'csv':
            _display_historical_csv(historical_prices)
            
    except Exception as e:
        console.print(f"[red]Error fetching historical data: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@data.command()
@click.argument('symbols', nargs=-1)
@click.option('--currency', '-c', default='usd', help='Target currency (default: usd)')
@click.pass_context
@async_command
async def refresh(ctx, symbols: tuple, currency: str):
    """Refresh cached price data for cryptocurrencies.
    
    Examples:
        crypto-portfolio data refresh BTC ETH
        crypto-portfolio data refresh  # Refresh all cached data
    """
    app_ctx = get_current_context()
    
    if app_ctx.dry_run:
        if symbols:
            console.print(f"[yellow]DRY RUN: Would refresh data for {', '.join(symbols)}[/yellow]")
        else:
            console.print("[yellow]DRY RUN: Would refresh all cached data[/yellow]")
        return
    
    try:
        data_service = await get_data_service()
        
        if symbols:
            # Refresh specific symbols
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Refreshing data for {len(symbols)} symbols...", total=None)
                
                results = await data_service.refresh_price_data(list(symbols), currency)
                
                progress.update(task, completed=True)
            
            # Display results
            table = Table(title="Refresh Results", box=box.ROUNDED)
            table.add_column("Symbol", style="cyan")
            table.add_column("Status", style="green")
            
            for symbol, success in results.items():
                status = "✓ Success" if success else "✗ Failed"
                style = "green" if success else "red"
                table.add_row(symbol, f"[{style}]{status}[/{style}]")
            
            console.print(table)
        else:
            # Clear all cache
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Clearing all cached data...", total=None)
                
                cleared_count = await data_service.clear_cache()
                
                progress.update(task, completed=True)
            
            console.print(f"[green]Cleared {cleared_count} cached entries[/green]")
            
    except Exception as e:
        console.print(f"[red]Error refreshing data: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


@data.command()
@click.pass_context
@async_command
async def status(ctx):
    """Show data service status and statistics."""
    app_ctx = get_current_context()
    
    try:
        data_service = await get_data_service()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Checking service status...", total=None)
            
            # Get health check and cache stats
            health = await data_service.health_check()
            cache_stats = await data_service.get_cache_stats()
            
            progress.update(task, completed=True)
        
        # Display health status
        health_table = Table(title="Service Health", box=box.ROUNDED)
        health_table.add_column("Component", style="cyan")
        health_table.add_column("Status", style="green")
        
        # Database status
        db_status = "✓ Healthy" if health.get('database') else "✗ Unhealthy"
        db_style = "green" if health.get('database') else "red"
        health_table.add_row("Database", f"[{db_style}]{db_status}[/{db_style}]")
        
        # Cache status
        cache_status = "✓ Healthy" if health.get('cache') else "✗ Unhealthy"
        cache_style = "green" if health.get('cache') else "red"
        health_table.add_row("Cache", f"[{cache_style}]{cache_status}[/{cache_style}]")
        
        # API clients status
        for client_name, client_healthy in health.get('api_clients', {}).items():
            client_status = "✓ Healthy" if client_healthy else "✗ Unhealthy"
            client_style = "green" if client_healthy else "red"
            health_table.add_row(f"API ({client_name})", f"[{client_style}]{client_status}[/{client_style}]")
        
        console.print(health_table)
        
        # Display cache statistics
        if cache_stats:
            cache_table = Table(title="Cache Statistics", box=box.ROUNDED)
            cache_table.add_column("Metric", style="cyan")
            cache_table.add_column("Value", style="green")
            
            cache_table.add_row("Cache Hits", str(cache_stats.get('hits', 0)))
            cache_table.add_row("Cache Misses", str(cache_stats.get('misses', 0)))
            cache_table.add_row("Hit Rate", f"{cache_stats.get('hit_rate', 0):.1f}%")
            cache_table.add_row("Current Size", str(cache_stats.get('size', 0)))
            cache_table.add_row("Max Size", str(cache_stats.get('max_size', 0)))
            cache_table.add_row("Evictions", str(cache_stats.get('evictions', 0)))
            
            console.print(cache_table)
            
    except Exception as e:
        console.print(f"[red]Error getting service status: {e}[/red]")
        if app_ctx.debug:
            console.print_exception()


def _display_prices_table(prices, currency: str):
    """Display prices in table format."""
    table = Table(title=f"Current Prices ({currency.upper()})", box=box.ROUNDED)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Price", style="green", justify="right")
    table.add_column("24h Change", justify="right")
    table.add_column("Market Cap", style="blue", justify="right")
    table.add_column("Volume 24h", style="yellow", justify="right")
    table.add_column("Last Updated", style="dim")
    
    for price in prices:
        # Format price change
        change_24h = price.price_change_percentage_24h
        if change_24h is not None:
            change_color = "green" if change_24h >= 0 else "red"
            change_text = f"[{change_color}]{change_24h:+.2f}%[/{change_color}]"
        else:
            change_text = "N/A"
        
        # Format market cap
        market_cap = f"${price.market_cap:,.0f}" if price.market_cap else "N/A"
        
        # Format volume
        volume = f"${price.volume_24h:,.0f}" if price.volume_24h else "N/A"
        
        # Format last updated
        last_updated = price.last_updated.strftime("%H:%M:%S")
        
        table.add_row(
            price.symbol,
            price.name,
            f"${price.current_price:,.8f}".rstrip('0').rstrip('.'),
            change_text,
            market_cap,
            volume,
            last_updated
        )
    
    console.print(table)


def _display_prices_json(prices):
    """Display prices in JSON format."""
    import json
    price_data = [price.to_dict() for price in prices]
    console.print(json.dumps(price_data, indent=2, default=str))


def _display_prices_csv(prices):
    """Display prices in CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Symbol', 'Name', 'Price', 'Currency', 'Market Cap', 'Volume 24h', 
                     'Price Change 24h %', 'Last Updated'])
    
    # Write data
    for price in prices:
        writer.writerow([
            price.symbol,
            price.name,
            float(price.current_price),
            price.currency,
            float(price.market_cap) if price.market_cap else '',
            float(price.volume_24h) if price.volume_24h else '',
            price.price_change_percentage_24h or '',
            price.last_updated.isoformat()
        ])
    
    console.print(output.getvalue())


def _display_historical_table(historical_prices, symbol: str, currency: str):
    """Display historical prices in table format."""
    table = Table(title=f"Historical Prices for {symbol} ({currency.upper()})", box=box.ROUNDED)
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="dim")
    table.add_column("Price", style="green", justify="right")
    table.add_column("Volume", style="yellow", justify="right")
    table.add_column("Market Cap", style="blue", justify="right")
    
    # Show last 20 entries for table display
    display_prices = historical_prices[-20:] if len(historical_prices) > 20 else historical_prices
    
    for price in display_prices:
        volume = f"${price.volume:,.0f}" if price.volume else "N/A"
        market_cap = f"${price.market_cap:,.0f}" if price.market_cap else "N/A"
        
        table.add_row(
            price.timestamp.strftime("%Y-%m-%d"),
            price.timestamp.strftime("%H:%M:%S"),
            f"${price.price:,.8f}".rstrip('0').rstrip('.'),
            volume,
            market_cap
        )
    
    if len(historical_prices) > 20:
        console.print(f"[dim]Showing last 20 of {len(historical_prices)} records[/dim]")
    
    console.print(table)


def _display_historical_json(historical_prices):
    """Display historical prices in JSON format."""
    import json
    price_data = [price.__dict__ for price in historical_prices]
    console.print(json.dumps(price_data, indent=2, default=str))


def _display_historical_csv(historical_prices):
    """Display historical prices in CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Symbol', 'Timestamp', 'Price', 'Currency', 'Volume', 'Market Cap'])
    
    # Write data
    for price in historical_prices:
        writer.writerow([
            price.symbol,
            price.timestamp.isoformat(),
            float(price.price),
            price.currency,
            float(price.volume) if price.volume else '',
            float(price.market_cap) if price.market_cap else ''
        ])
    
    console.print(output.getvalue())

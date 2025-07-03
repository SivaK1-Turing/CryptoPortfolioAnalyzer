"""CLI commands for real-time data streaming and monitoring."""

import asyncio
import click
import json
import time
from typing import Optional, List
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..streaming.manager import StreamManager, StreamConfig
from ..streaming.websocket_server import WebSocketServer
from ..streaming.price_feeds import PriceFeedManager, PriceFeedProvider, MockPriceFeed
from ..streaming.portfolio_monitor import PortfolioMonitor, AlertRule, AlertType, AlertSeverity
from ..streaming.events import StreamEventBus, EventFilter, EventType
from ..analytics.portfolio import PortfolioAnalyzer
from ..data.database import DatabaseManager

console = Console()


@click.group()
def stream():
    """Real-time data streaming commands."""
    pass


@stream.command()
@click.option('--host', default='localhost', help='WebSocket server host')
@click.option('--port', default=8000, help='WebSocket server port')
@click.option('--symbols', default='BTC,ETH,ADA', help='Comma-separated list of symbols to stream')
@click.option('--provider', type=click.Choice(['binance', 'coinbase', 'mock']), 
              default='mock', help='Price feed provider')
@click.option('--dashboard/--no-dashboard', default=True, help='Open dashboard in browser')
async def start(host: str, port: int, symbols: str, provider: str, dashboard: bool):
    """Start real-time streaming server."""
    console.print("[bold green]Starting real-time streaming server...[/bold green]")
    
    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(',')]
    
    try:
        # Initialize components
        event_bus = StreamEventBus()
        websocket_server = WebSocketServer(host=host, port=port)
        price_feed_manager = PriceFeedManager()
        
        # Add price feed provider
        provider_enum = PriceFeedProvider(provider)
        price_feed_manager.add_provider(provider_enum, symbol_list, is_primary=True)
        
        # Set up portfolio monitoring (if portfolio exists)
        try:
            db_manager = DatabaseManager()
            portfolio_analyzer = PortfolioAnalyzer(db_manager)
            portfolio_monitor = PortfolioMonitor(portfolio_analyzer)
            portfolio_monitor.set_price_feed_manager(price_feed_manager)
            
            # Add some default alert rules
            portfolio_monitor.add_alert_rule(AlertRule(
                rule_id="btc_price_alert",
                alert_type=AlertType.PRICE_THRESHOLD,
                symbol="BTC",
                threshold_value=60000,
                severity=AlertSeverity.INFO
            ))
            
            portfolio_monitor.add_alert_rule(AlertRule(
                rule_id="portfolio_value_alert",
                alert_type=AlertType.PORTFOLIO_VALUE,
                threshold_value=100000,
                severity=AlertSeverity.WARNING
            ))
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not initialize portfolio monitoring: {e}[/yellow]")
            portfolio_monitor = None
        
        # Start all components
        await event_bus.start()
        await websocket_server.start()
        await price_feed_manager.start()
        
        if portfolio_monitor:
            await portfolio_monitor.start()
        
        # Set up event handlers
        from ..streaming.events import WebSocketEventHandler
        websocket_handler = WebSocketEventHandler(websocket_server)
        event_bus.subscribe("websocket_handler", websocket_handler)
        
        # Connect price feed to event bus
        def price_update_handler(price_update):
            asyncio.create_task(event_bus.publish_price_update(
                price_update.symbol, 
                price_update.to_dict(),
                source=f"{provider}_feed"
            ))
        
        price_feed_manager.add_handler(price_update_handler)
        
        # Connect portfolio monitor to event bus
        if portfolio_monitor:
            def portfolio_update_handler(snapshot):
                asyncio.create_task(event_bus.publish_portfolio_update(
                    snapshot.to_dict(),
                    source="portfolio_monitor"
                ))
            
            def alert_handler(alert):
                asyncio.create_task(event_bus.publish_alert(
                    alert.to_dict(),
                    source="alert_system"
                ))
            
            portfolio_monitor.add_portfolio_handler(portfolio_update_handler)
            portfolio_monitor.add_alert_handler(alert_handler)
        
        console.print(f"[bold green]✓[/bold green] Streaming server started on {host}:{port}")
        console.print(f"[bold green]✓[/bold green] Price feed: {provider} ({', '.join(symbol_list)})")
        console.print(f"[bold green]✓[/bold green] Dashboard: http://{host}:{port}")
        
        if dashboard:
            import webbrowser
            webbrowser.open(f"http://{host}:{port}")
        
        console.print("\n[bold yellow]Press Ctrl+C to stop the server[/bold yellow]")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold red]Stopping streaming server...[/bold red]")
        
        # Cleanup
        if portfolio_monitor:
            await portfolio_monitor.stop()
        await price_feed_manager.stop()
        await websocket_server.stop()
        await event_bus.stop()
        
        console.print("[bold green]✓[/bold green] Streaming server stopped")
        
    except Exception as e:
        console.print(f"[bold red]Error starting streaming server: {e}[/bold red]")
        raise click.ClickException(str(e))


@stream.command()
@click.option('--symbols', default='BTC,ETH,ADA', help='Comma-separated list of symbols to monitor')
@click.option('--provider', type=click.Choice(['binance', 'coinbase', 'mock']), 
              default='mock', help='Price feed provider')
@click.option('--refresh', default=1.0, help='Refresh interval in seconds')
async def monitor(symbols: str, provider: str, refresh: float):
    """Monitor real-time price feeds in terminal."""
    symbol_list = [s.strip().upper() for s in symbols.split(',')]
    
    console.print(f"[bold green]Starting price monitor for {', '.join(symbol_list)}...[/bold green]")
    
    # Initialize price feed
    price_feed_manager = PriceFeedManager()
    provider_enum = PriceFeedProvider(provider)
    price_feed_manager.add_provider(provider_enum, symbol_list, is_primary=True)
    
    # Store latest prices
    latest_prices = {}
    
    def price_update_handler(price_update):
        latest_prices[price_update.symbol] = price_update
    
    price_feed_manager.add_handler(price_update_handler)
    
    try:
        await price_feed_manager.start()
        
        def create_price_table():
            """Create a table showing current prices."""
            table = Table(title="Real-time Cryptocurrency Prices")
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Price", style="green", justify="right")
            table.add_column("24h Change", justify="right")
            table.add_column("Volume", justify="right")
            table.add_column("Last Update", style="dim")
            
            for symbol in symbol_list:
                if symbol in latest_prices:
                    price_update = latest_prices[symbol]
                    
                    # Format price
                    price_str = f"${price_update.price:,.2f}"
                    
                    # Format 24h change
                    if price_update.change_percent_24h is not None:
                        change_color = "green" if price_update.change_percent_24h >= 0 else "red"
                        change_str = f"[{change_color}]{price_update.change_percent_24h:+.2f}%[/{change_color}]"
                    else:
                        change_str = "N/A"
                    
                    # Format volume
                    if price_update.volume_24h:
                        volume_str = f"${price_update.volume_24h:,.0f}"
                    else:
                        volume_str = "N/A"
                    
                    # Format timestamp
                    time_str = price_update.timestamp.strftime("%H:%M:%S")
                    
                    table.add_row(symbol, price_str, change_str, volume_str, time_str)
                else:
                    table.add_row(symbol, "Waiting...", "N/A", "N/A", "N/A")
            
            return table
        
        # Live display
        with Live(create_price_table(), refresh_per_second=1/refresh, console=console) as live:
            try:
                while True:
                    await asyncio.sleep(refresh)
                    live.update(create_price_table())
            except KeyboardInterrupt:
                pass
        
    finally:
        await price_feed_manager.stop()
        console.print("\n[bold green]✓[/bold green] Price monitor stopped")


@stream.command()
@click.option('--host', default='localhost', help='WebSocket server host')
@click.option('--port', default=8000, help='WebSocket server port')
async def status(host: str, port: int):
    """Check status of streaming server."""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{host}:{port}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Create status table
                    table = Table(title="Streaming Server Status")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    
                    table.add_row("Status", data.get("status", "unknown"))
                    table.add_row("Connected Clients", str(data.get("connected_clients", 0)))
                    table.add_row("Uptime", f"{data.get('uptime', 0):.1f} seconds")
                    
                    # Show room information
                    rooms = data.get("rooms", {})
                    if rooms:
                        table.add_row("", "")  # Separator
                        for room_name, client_count in rooms.items():
                            table.add_row(f"Room: {room_name}", str(client_count))
                    
                    console.print(table)
                else:
                    console.print(f"[bold red]Server returned status {response.status}[/bold red]")
                    
    except aiohttp.ClientConnectorError:
        console.print(f"[bold red]Could not connect to server at {host}:{port}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error checking server status: {e}[/bold red]")


@stream.command()
@click.option('--symbols', default='BTC,ETH', help='Comma-separated list of symbols')
@click.option('--duration', default=60, help='Test duration in seconds')
async def test(symbols: str, duration: int):
    """Test streaming components with mock data."""
    symbol_list = [s.strip().upper() for s in symbols.split(',')]
    
    console.print(f"[bold green]Testing streaming components for {duration} seconds...[/bold green]")
    
    # Initialize components
    event_bus = StreamEventBus()
    price_feed_manager = PriceFeedManager()
    
    # Add mock price feed
    price_feed_manager.add_provider(PriceFeedProvider.MOCK, symbol_list, is_primary=True)
    
    # Event counters
    event_counts = {event_type: 0 for event_type in EventType}
    
    def event_handler(event):
        event_counts[event.event_type] += 1
    
    # Subscribe to all events
    event_bus.subscribe("test_handler", event_handler)
    
    # Connect price feed to event bus
    def price_update_handler(price_update):
        asyncio.create_task(event_bus.publish_price_update(
            price_update.symbol, 
            price_update.to_dict(),
            source="mock_feed"
        ))
    
    price_feed_manager.add_handler(price_update_handler)
    
    try:
        # Start components
        await event_bus.start()
        await price_feed_manager.start()
        
        # Progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running test...", total=duration)
            
            for i in range(duration):
                await asyncio.sleep(1)
                progress.update(task, advance=1)
        
        # Show results
        console.print("\n[bold green]Test Results:[/bold green]")
        
        results_table = Table()
        results_table.add_column("Component", style="cyan")
        results_table.add_column("Status", style="green")
        results_table.add_column("Events", justify="right")
        
        # Event bus stats
        bus_stats = event_bus.get_bus_stats()
        results_table.add_row(
            "Event Bus",
            "✓ Running" if bus_stats["running"] else "✗ Stopped",
            f"{bus_stats['events_processed']}"
        )
        
        # Price feed stats
        provider_status = price_feed_manager.get_provider_status()
        for provider, status in provider_status.items():
            results_table.add_row(
                f"Price Feed ({provider})",
                "✓ Running" if status["running"] else "✗ Stopped",
                f"{len(status['symbols'])} symbols"
            )
        
        # Event type breakdown
        results_table.add_row("", "", "")  # Separator
        for event_type, count in event_counts.items():
            if count > 0:
                results_table.add_row(
                    f"  {event_type.value}",
                    "",
                    str(count)
                )
        
        console.print(results_table)
        
    finally:
        await price_feed_manager.stop()
        await event_bus.stop()
        console.print("\n[bold green]✓[/bold green] Test completed")


@stream.command()
@click.option('--symbol', required=True, help='Symbol to set alert for')
@click.option('--price', type=float, help='Price threshold')
@click.option('--change', type=float, help='Percentage change threshold')
@click.option('--severity', type=click.Choice(['info', 'warning', 'critical']), 
              default='info', help='Alert severity')
async def alert(symbol: str, price: Optional[float], change: Optional[float], severity: str):
    """Set up price alerts (requires running server)."""
    if not price and not change:
        raise click.ClickException("Must specify either --price or --change threshold")
    
    console.print(f"[bold green]Setting up alert for {symbol.upper()}...[/bold green]")
    
    # This would typically connect to a running server to configure alerts
    # For now, just show what would be configured
    
    alert_config = {
        "symbol": symbol.upper(),
        "severity": severity
    }
    
    if price:
        alert_config["price_threshold"] = price
        console.print(f"[green]✓[/green] Price alert: {symbol.upper()} >= ${price:,.2f}")
    
    if change:
        alert_config["change_threshold"] = change
        console.print(f"[green]✓[/green] Change alert: {symbol.upper()} >= {change:+.1f}%")
    
    console.print(f"[green]✓[/green] Severity: {severity}")
    console.print("\n[yellow]Note: This would be sent to a running streaming server[/yellow]")
    console.print(f"Alert configuration: {json.dumps(alert_config, indent=2)}")


# Make commands async-compatible
def make_async_command(func):
    """Decorator to make async commands work with Click."""
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

# Apply async wrapper to commands
start.callback = make_async_command(start.callback)
monitor.callback = make_async_command(monitor.callback)
status.callback = make_async_command(status.callback)
test.callback = make_async_command(test.callback)
alert.callback = make_async_command(alert.callback)

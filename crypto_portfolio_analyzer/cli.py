"""
Main CLI module with hierarchical command tree and context inheritance.

This module provides the main entry point for the CLI application with support
for hierarchical commands, context inheritance, plugin discovery, and a hidden
debug REPL command for development.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from crypto_portfolio_analyzer.core.context import (
    AppContext,
    get_current_context,
    set_context,
    inherit_context,
    with_context
)
from crypto_portfolio_analyzer.core.plugin_manager import PluginManager
from crypto_portfolio_analyzer.core.config import ConfigManager
from crypto_portfolio_analyzer.core.events import get_event_bus, start_event_bus, stop_event_bus, EventType
from crypto_portfolio_analyzer.core.logging import setup_logging as setup_structured_logging, capture_exception

# Global instances
console = Console()
logger = logging.getLogger(__name__)


# ContextAware classes moved to core.cli_base to avoid circular imports
from .core.cli_base import ContextAwareGroup, ContextAwareCommand


def setup_logging(debug: bool = False, verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    
    # Configure rich logging
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    
    # Set specific logger levels
    logging.getLogger("crypto_portfolio_analyzer").setLevel(level)
    logging.getLogger("watchdog").setLevel(logging.WARNING)


async def initialize_app(ctx: click.Context) -> None:
    """Initialize the application components."""
    app_ctx = get_current_context()
    
    try:
        # Start event bus
        await start_event_bus()
        event_bus = get_event_bus()
        
        # Publish app starting event
        await event_bus.publish_event(
            EventType.APP_STARTING,
            "cli",
            {"command": ctx.info_name}
        )
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        await config_manager.initialize()
        app_ctx.config = config_manager.get_all()

        # Set up structured logging with configuration
        setup_structured_logging(app_ctx.config)
        
        # Initialize plugin manager
        plugins_dir = Path(config_manager.get("plugins.directory", "plugins"))
        hot_reload = config_manager.get("plugins.hot_reload", True)
        
        plugin_manager = PluginManager(plugins_dir, hot_reload)
        await plugin_manager.start()
        
        # Store managers in context
        app_ctx.plugins['config_manager'] = config_manager
        app_ctx.plugins['plugin_manager'] = plugin_manager
        app_ctx.plugins['event_bus'] = event_bus
        
        # Publish app started event
        await event_bus.publish_event(
            EventType.APP_STARTED,
            "cli",
            {"command": ctx.info_name, "plugins_loaded": len(plugin_manager.get_all_plugins())}
        )
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        capture_exception(e, {"context": "app_initialization"})
        raise click.ClickException(f"Initialization failed: {e}")


async def cleanup_app() -> None:
    """Clean up application components."""
    try:
        app_ctx = get_current_context()
        event_bus = get_event_bus()
        
        # Publish app stopping event
        await event_bus.publish_event(EventType.APP_STOPPING, "cli", {})
        
        # Stop plugin manager
        plugin_manager = app_ctx.plugins.get('plugin_manager')
        if plugin_manager:
            await plugin_manager.stop()
        
        # Publish app stopped event
        await event_bus.publish_event(EventType.APP_STOPPED, "cli", {})
        
        # Stop event bus
        await stop_event_bus()
        
        logger.info("Application cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


@click.group(cls=ContextAwareGroup, invoke_without_command=True)
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def main(ctx: click.Context, debug: bool, verbose: bool, config: Optional[str], dry_run: bool) -> None:
    """
    Crypto Portfolio Analyzer - A sophisticated CLI tool for cryptocurrency portfolio management.
    
    This tool provides comprehensive portfolio tracking, real-time price fetching,
    analytics, and reporting capabilities with a plugin-based architecture.
    """
    # Set up logging
    setup_logging(debug, verbose)
    
    # Create and set initial context
    app_ctx = AppContext(debug=debug, verbose=verbose, dry_run=dry_run)
    if config:
        app_ctx.config['config_file'] = config
    
    set_context(app_ctx)
    
    # If no subcommand is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    
    # Initialize application
    try:
        asyncio.run(initialize_app(ctx))
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application failed: {e}")
        capture_exception(e, {"context": "app_initialization"})
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command(cls=ContextAwareCommand, hidden=True)
@click.pass_context
def debug_repl(ctx: click.Context) -> None:
    """
    Hidden debug REPL command for development.
    
    Drops into an IPython shell with full application context available.
    This command is hidden from help output and only available in debug mode.
    """
    app_ctx = get_current_context()
    
    if not app_ctx.debug:
        raise click.ClickException("Debug REPL is only available in debug mode. Use --debug flag.")
    
    try:
        # Import IPython here so it can be mocked in tests
        import IPython

        # Prepare namespace with useful objects
        namespace = {
            'app_ctx': app_ctx,
            'config_manager': app_ctx.plugins.get('config_manager'),
            'plugin_manager': app_ctx.plugins.get('plugin_manager'),
            'event_bus': app_ctx.plugins.get('event_bus'),
            'click_ctx': ctx,
            'console': console,
        }

        console.print("[bold green]Debug REPL started[/bold green]")
        console.print("Available objects: app_ctx, config_manager, plugin_manager, event_bus, click_ctx, console")
        console.print("Use Ctrl+D or 'exit' to return to CLI")

        IPython.start_ipython(argv=[], user_ns=namespace)

    except ImportError:
        raise click.ClickException("IPython is required for debug REPL. Install with: pip install ipython")


@main.command(cls=ContextAwareCommand)
def version() -> None:
    """Show version information."""
    from crypto_portfolio_analyzer import __version__
    
    app_ctx = get_current_context()
    
    console.print(f"[bold]Crypto Portfolio Analyzer[/bold] v{__version__}")
    
    if app_ctx.verbose:
        # Show additional version info
        plugin_manager = app_ctx.plugins.get('plugin_manager')
        if plugin_manager:
            plugins = plugin_manager.list_plugins()
            console.print(f"Loaded plugins: {len(plugins)}")
            
            if app_ctx.debug:
                for plugin in plugins:
                    console.print(f"  - {plugin.name} v{plugin.version}")


@main.command(cls=ContextAwareCommand)
def plugins() -> None:
    """List loaded plugins and their status."""
    app_ctx = get_current_context()
    plugin_manager = app_ctx.plugins.get('plugin_manager')
    
    if not plugin_manager:
        console.print("[red]Plugin manager not available[/red]")
        return
    
    plugins = plugin_manager.list_plugins()
    
    if not plugins:
        console.print("[yellow]No plugins loaded[/yellow]")
        return
    
    console.print(f"[bold]Loaded Plugins ({len(plugins)})[/bold]")
    console.print()
    
    for plugin in plugins:
        status = "[green]✓[/green]" if plugin_manager.is_plugin_loaded(plugin.name) else "[red]✗[/red]"
        console.print(f"{status} [bold]{plugin.name}[/bold] v{plugin.version}")
        
        if app_ctx.verbose:
            console.print(f"    Author: {plugin.author}")
            console.print(f"    Module: {plugin.module_name}")
            if plugin.description and plugin.description != "No description":
                console.print(f"    Description: {plugin.description}")
            console.print()


# Note: Cleanup is handled by the main command context
# No atexit handler needed as cleanup happens naturally


# Register command groups - moved to avoid circular imports
def register_commands():
    """Register all command groups with the main CLI."""
    from crypto_portfolio_analyzer.commands.portfolio import portfolio_group
    from crypto_portfolio_analyzer.commands.config import config_group
    from crypto_portfolio_analyzer.commands.data import data
    from crypto_portfolio_analyzer.commands.analytics import analytics
    from crypto_portfolio_analyzer.commands.visualize import visualize

    main.add_command(portfolio_group)
    main.add_command(config_group)
    main.add_command(data)
    main.add_command(analytics)
    main.add_command(visualize)

# Register commands when module is imported
register_commands()


if __name__ == '__main__':
    main()

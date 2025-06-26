"""
Configuration management commands.

This module provides commands for managing application configuration including
viewing current settings, updating configuration values, and managing secrets.
"""

import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
import yaml
import json

from crypto_portfolio_analyzer.cli import ContextAwareGroup, ContextAwareCommand
from crypto_portfolio_analyzer.core.context import get_current_context

console = Console()


@click.group(cls=ContextAwareGroup, name='config')
def config_group() -> None:
    """Configuration management commands."""
    pass


@config_group.command(cls=ContextAwareCommand, name='show')
@click.option('--key', help='Show specific configuration key')
@click.option('--format', 'output_format', type=click.Choice(['yaml', 'json', 'table']), 
              default='yaml', help='Output format')
def show_config(key: str = None, output_format: str = 'yaml') -> None:
    """Show current configuration."""
    app_ctx = get_current_context()
    config_manager = app_ctx.plugins.get('config_manager')
    
    if not config_manager:
        console.print("[red]Configuration manager not available[/red]")
        return
    
    if key:
        # Show specific key
        value = config_manager.get(key)
        if value is None:
            console.print(f"[red]Configuration key '{key}' not found[/red]")
            return
        
        console.print(f"[bold]{key}:[/bold]")
        
        if output_format == 'json':
            console.print(json.dumps(value, indent=2))
        elif output_format == 'yaml':
            console.print(yaml.dump({key: value}, default_flow_style=False))
        else:
            console.print(str(value))
    
    else:
        # Show all configuration
        config = config_manager.get_all()
        
        if output_format == 'table':
            _show_config_table(config)
        elif output_format == 'json':
            syntax = Syntax(json.dumps(config, indent=2), "json", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:  # yaml
            syntax = Syntax(yaml.dump(config, default_flow_style=False), "yaml", theme="monokai", line_numbers=True)
            console.print(syntax)


def _show_config_table(config: dict, prefix: str = "") -> None:
    """Show configuration in table format."""
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_column("Type", style="yellow")
    
    def add_config_rows(data: dict, current_prefix: str = ""):
        for key, value in data.items():
            full_key = f"{current_prefix}.{key}" if current_prefix else key
            
            if isinstance(value, dict):
                # Add section header
                table.add_row(f"[bold]{full_key}[/bold]", "[dim]<section>[/dim]", "dict")
                add_config_rows(value, full_key)
            else:
                # Add value row
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                
                table.add_row(full_key, value_str, type(value).__name__)
    
    add_config_rows(config)
    console.print(table)


@config_group.command(cls=ContextAwareCommand, name='set')
@click.argument('key')
@click.argument('value')
@click.option('--type', 'value_type', type=click.Choice(['str', 'int', 'float', 'bool']), 
              default='str', help='Value type')
def set_config(key: str, value: str, value_type: str) -> None:
    """Set a configuration value."""
    app_ctx = get_current_context()
    config_manager = app_ctx.plugins.get('config_manager')
    
    if not config_manager:
        console.print("[red]Configuration manager not available[/red]")
        return
    
    # Convert value to appropriate type
    try:
        if value_type == 'int':
            converted_value = int(value)
        elif value_type == 'float':
            converted_value = float(value)
        elif value_type == 'bool':
            converted_value = value.lower() in ('true', '1', 'yes', 'on')
        else:
            converted_value = value
        
        if app_ctx.dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would set {key} = {converted_value} ({value_type})")
            return
        
        config_manager.set(key, converted_value)
        console.print(f"[green]✓[/green] Set {key} = {converted_value}")
        
    except ValueError as e:
        console.print(f"[red]Error converting value:[/red] {e}")


@config_group.command(cls=ContextAwareCommand, name='get')
@click.argument('key')
def get_config(key: str) -> None:
    """Get a specific configuration value."""
    app_ctx = get_current_context()
    config_manager = app_ctx.plugins.get('config_manager')
    
    if not config_manager:
        console.print("[red]Configuration manager not available[/red]")
        return
    
    value = config_manager.get(key)
    if value is None:
        console.print(f"[red]Configuration key '{key}' not found[/red]")
        return
    
    console.print(f"[bold]{key}:[/bold] {value}")


@config_group.command(cls=ContextAwareCommand, name='secrets')
@click.option('--list', 'list_secrets', is_flag=True, help='List available secrets')
@click.option('--set', 'set_secret', nargs=2, metavar='KEY VALUE', help='Set a secret value')
@click.option('--get', 'get_secret', help='Get a secret value')
@click.option('--delete', 'delete_secret', help='Delete a secret')
def manage_secrets(list_secrets: bool, set_secret: tuple, get_secret: str, delete_secret: str) -> None:
    """Manage encrypted secrets."""
    app_ctx = get_current_context()
    config_manager = app_ctx.plugins.get('config_manager')
    
    if not config_manager:
        console.print("[red]Configuration manager not available[/red]")
        return
    
    import asyncio
    
    async def _manage_secrets():
        if list_secrets:
            # List secrets (keys only, not values)
            secrets = await config_manager._secret_manager.load_secrets()
            if not secrets:
                console.print("[yellow]No secrets configured[/yellow]")
                return
            
            console.print("[bold]Available Secrets:[/bold]")
            for key in secrets.keys():
                console.print(f"  • {key}")
        
        elif set_secret:
            key, value = set_secret
            if app_ctx.dry_run:
                console.print(f"[yellow]DRY RUN:[/yellow] Would set secret '{key}'")
                return
            
            await config_manager.set_secret(key, value)
            console.print(f"[green]✓[/green] Secret '{key}' set successfully")
        
        elif get_secret:
            value = await config_manager.get_secret(get_secret)
            if value is None:
                console.print(f"[red]Secret '{get_secret}' not found[/red]")
                return
            
            console.print(f"[bold]{get_secret}:[/bold] {value}")
        
        elif delete_secret:
            if app_ctx.dry_run:
                console.print(f"[yellow]DRY RUN:[/yellow] Would delete secret '{delete_secret}'")
                return
            
            success = await config_manager._secret_manager.delete_secret(delete_secret)
            if success:
                console.print(f"[green]✓[/green] Secret '{delete_secret}' deleted")
            else:
                console.print(f"[red]Secret '{delete_secret}' not found[/red]")
        
        else:
            console.print("[yellow]Please specify an action: --list, --set, --get, or --delete[/yellow]")
    
    asyncio.run(_manage_secrets())


@config_group.command(cls=ContextAwareCommand, name='validate')
def validate_config() -> None:
    """Validate current configuration."""
    app_ctx = get_current_context()
    config_manager = app_ctx.plugins.get('config_manager')
    
    if not config_manager:
        console.print("[red]Configuration manager not available[/red]")
        return
    
    console.print("[bold]Configuration Validation[/bold]")
    console.print()
    
    # Basic validation checks
    issues = []
    config = config_manager.get_all()
    
    # Check required sections
    required_sections = ['app', 'logging', 'plugins']
    for section in required_sections:
        if section not in config:
            issues.append(f"Missing required section: {section}")
    
    # Check logging configuration
    if 'logging' in config:
        log_config = config['logging']
        if 'level' not in log_config:
            issues.append("Missing logging.level configuration")
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_config.get('level') not in valid_levels:
            issues.append(f"Invalid logging level: {log_config.get('level')}")
    
    # Check plugin configuration
    if 'plugins' in config:
        plugin_config = config['plugins']
        if 'directory' not in plugin_config:
            issues.append("Missing plugins.directory configuration")
    
    # Display results
    if issues:
        console.print("[red]Configuration Issues Found:[/red]")
        for issue in issues:
            console.print(f"  • {issue}")
    else:
        console.print("[green]✓ Configuration is valid[/green]")


# Register the config group with the main CLI
# This would typically be done through entry points in pyproject.toml

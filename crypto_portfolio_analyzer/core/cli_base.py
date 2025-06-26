"""Base CLI classes to avoid circular imports."""

import click
from typing import Any

from .context import get_current_context, inherit_context, set_context, AppContext


class ContextAwareGroup(click.Group):
    """
    Custom Click Group that provides context inheritance.

    This group ensures that subcommands inherit the parent context
    while maintaining their own isolated state.
    """

    def invoke(self, ctx: click.Context) -> Any:
        """Invoke the group with context inheritance."""
        # Get or create app context
        try:
            app_ctx = get_current_context()
        except ValueError:
            app_ctx = AppContext()
            set_context(app_ctx)

        # Push current command to stack
        app_ctx.push_command(ctx.info_name)

        # Store Click context in app context
        app_ctx.metadata['click_context'] = ctx

        try:
            return super().invoke(ctx)
        finally:
            app_ctx.pop_command()


class ContextAwareCommand(click.Command):
    """
    Custom Click Command that inherits parent context.

    This command automatically inherits context from parent commands
    and provides access to the application state.
    """

    def invoke(self, ctx: click.Context) -> Any:
        """Invoke the command with inherited context."""
        # Inherit context from parent
        app_ctx = inherit_context()
        app_ctx.push_command(ctx.info_name)
        app_ctx.metadata['click_context'] = ctx

        # Set the inherited context
        set_context(app_ctx)

        try:
            return super().invoke(ctx)
        finally:
            app_ctx.pop_command()

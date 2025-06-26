"""
Application context management using ContextVar for hierarchical command inheritance.

This module provides a thread-safe context system that allows subcommands to inherit
parent context while maintaining isolation between different command executions.
"""

import asyncio
from contextvars import ContextVar as StdContextVar, copy_context
from typing import Any, Dict, Optional, TypeVar, Generic, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class AppContext:
    """
    Application context that holds global state and configuration.

    This context is passed down through the command hierarchy and can be
    extended by plugins and subcommands.
    """
    config: Dict[str, Any] = field(default_factory=dict)
    plugins: Dict[str, Any] = field(default_factory=dict)
    debug: bool = False
    verbose: bool = False
    dry_run: bool = False
    command_stack: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def copy(self) -> 'AppContext':
        """Create a copy of the context for inheritance."""
        return AppContext(
            config=self.config.copy(),
            plugins=self.plugins.copy(),
            debug=self.debug,
            verbose=self.verbose,
            dry_run=self.dry_run,
            command_stack=self.command_stack.copy(),
            metadata=self.metadata.copy()
        )

    def push_command(self, command_name: str) -> None:
        """Push a command onto the command stack."""
        self.command_stack.append(command_name)
        logger.debug(f"Command stack: {' -> '.join(self.command_stack)}")

    def pop_command(self) -> Optional[str]:
        """Pop the last command from the stack."""
        if self.command_stack:
            command = self.command_stack.pop()
            logger.debug(f"Popped command: {command}, remaining: {' -> '.join(self.command_stack)}")
            return command
        return None


class EnhancedContextVar(Generic[T]):
    """
    Custom ContextVar wrapper that provides enhanced functionality.

    This wrapper adds logging, validation, and hierarchical inheritance
    capabilities to the standard ContextVar.
    """

    def __init__(self, name: str, default: Optional[T] = None):
        self._var: StdContextVar[T] = StdContextVar(name, default=default)
        self._name = name
        self._default = default
        
    def get(self, default: Optional[T] = None) -> T:
        """Get the current context value with optional default."""
        try:
            value = self._var.get()
            logger.debug(f"Retrieved context {self._name}: {type(value).__name__}")
            return value
        except LookupError:
            result = default if default is not None else self._default
            if result is None:
                raise ValueError(f"No value set for context variable '{self._name}' and no default provided")
            logger.debug(f"Using default for context {self._name}: {type(result).__name__}")
            return result
    
    def set(self, value: T) -> None:
        """Set the context value."""
        logger.debug(f"Setting context {self._name}: {type(value).__name__}")
        self._var.set(value)
    
    def reset(self, token) -> None:
        """Reset the context to a previous state."""
        logger.debug(f"Resetting context {self._name}")
        self._var.reset(token)


# Global application context
app_context: EnhancedContextVar[AppContext] = EnhancedContextVar('app_context', AppContext())


def get_current_context() -> AppContext:
    """Get the current application context."""
    return app_context.get()


def set_context(context: AppContext) -> None:
    """Set the application context."""
    app_context.set(context)


def with_context(context: AppContext):
    """
    Decorator to run a function with a specific context.
    
    Args:
        context: The context to use for the function execution
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            token = app_context.set(context)
            try:
                return func(*args, **kwargs)
            finally:
                app_context.reset(token)
        return wrapper
    return decorator


async def with_context_async(context: AppContext):
    """
    Async context manager for running code with a specific context.
    
    Args:
        context: The context to use
        
    Usage:
        async with with_context_async(my_context):
            # Code here runs with my_context
            pass
    """
    token = app_context.set(context)
    try:
        yield context
    finally:
        app_context.reset(token)


def inherit_context() -> AppContext:
    """
    Create a new context that inherits from the current context.
    
    This is used by subcommands to inherit parent context while
    maintaining their own isolated state.
    
    Returns:
        New context that inherits from current context
    """
    try:
        current = get_current_context()
        inherited = current.copy()
        logger.debug(f"Inherited context from command stack: {' -> '.join(current.command_stack)}")
        return inherited
    except ValueError:
        # No current context, create a new one
        logger.debug("No current context found, creating new context")
        return AppContext()


def run_in_context(func: Callable, context: AppContext, *args, **kwargs):
    """
    Run a function in a specific context using copy_context().
    
    This ensures complete isolation between different command executions.
    
    Args:
        func: Function to run
        context: Context to use
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    ctx = copy_context()
    
    def _run():
        set_context(context)
        return func(*args, **kwargs)
    
    return ctx.run(_run)


async def run_in_context_async(func: Callable, context: AppContext, *args, **kwargs):
    """
    Run an async function in a specific context.
    
    Args:
        func: Async function to run
        context: Context to use
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    async with with_context_async(context):
        return await func(*args, **kwargs)

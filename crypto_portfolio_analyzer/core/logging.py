"""
Structured logging system with dynamic sampling and Sentry integration.

This module provides comprehensive logging capabilities including JSON structured
logging, dynamic sampling for DEBUG logs, and integration with Sentry for
critical error reporting and performance monitoring.
"""

import json
import logging
import logging.handlers
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import traceback

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured JSON logging.
    
    Converts log records to structured JSON format with additional metadata
    including context information, performance metrics, and error details.
    """
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add process and thread info
        log_data.update({
            "process_id": record.process,
            "thread_id": record.thread,
            "thread_name": record.threadName,
        })
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if enabled
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'getMessage', 'exc_info',
                    'exc_text', 'stack_info'
                }:
                    try:
                        # Only include JSON-serializable values
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_data["extra"] = extra_fields
        
        return json.dumps(log_data, default=str)


class SamplingFilter(logging.Filter):
    """
    Logging filter that implements dynamic sampling.
    
    Reduces the volume of DEBUG logs by only allowing a percentage
    of them through, helping to reduce noise while maintaining
    observability.
    """
    
    def __init__(self, sample_rate: float = 0.01):
        super().__init__()
        self.sample_rate = sample_rate
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records based on sampling rate."""
        # Always allow non-DEBUG logs
        if record.levelno > logging.DEBUG:
            return True
        
        # Sample DEBUG logs
        return random.random() < self.sample_rate


class ContextFilter(logging.Filter):
    """
    Logging filter that adds application context to log records.
    
    Enriches log records with current application context including
    command stack, user information, and request IDs.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context information to log record."""
        try:
            from crypto_portfolio_analyzer.core.context import get_current_context
            
            app_ctx = get_current_context()
            
            # Add command stack
            if app_ctx.command_stack:
                record.command_stack = " -> ".join(app_ctx.command_stack)
                record.current_command = app_ctx.command_stack[-1]
            
            # Add debug/verbose flags
            record.debug_mode = app_ctx.debug
            record.verbose_mode = app_ctx.verbose
            record.dry_run_mode = app_ctx.dry_run
            
            # Add correlation ID if available
            if 'correlation_id' in app_ctx.metadata:
                record.correlation_id = app_ctx.metadata['correlation_id']
            
        except (ValueError, ImportError):
            # Context not available, continue without it
            pass
        
        return True


class LoggingManager:
    """
    Comprehensive logging management system.
    
    Handles setup and configuration of structured logging, dynamic sampling,
    Sentry integration, and multiple output handlers.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.handlers = []
        self.sentry_initialized = False
    
    def setup_logging(self) -> None:
        """Set up the complete logging system."""
        # Get logging configuration
        log_config = self.config.get('logging', {})
        
        # Set root logger level
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Set up handlers
        self._setup_console_handler(log_config)
        self._setup_file_handler(log_config)
        self._setup_sentry(log_config)
        
        # Add context filter to all handlers
        context_filter = ContextFilter()
        for handler in self.handlers:
            handler.addFilter(context_filter)
        
        # Set up sampling for DEBUG logs
        sampling_rate = log_config.get('sampling_rate', 0.01)
        if sampling_rate < 1.0:
            sampling_filter = SamplingFilter(sampling_rate)
            for handler in self.handlers:
                if handler.level <= logging.DEBUG:
                    handler.addFilter(sampling_filter)
        
        # Add handlers to root logger
        for handler in self.handlers:
            root_logger.addHandler(handler)
        
        # Set specific logger levels
        logging.getLogger('crypto_portfolio_analyzer').setLevel(level)
        logging.getLogger('watchdog').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
    
    def _setup_console_handler(self, log_config: Dict[str, Any]) -> None:
        """Set up console logging handler."""
        console_config = log_config.get('handlers', {}).get('console', {})
        
        if not console_config.get('enabled', True):
            return
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, console_config.get('level', 'INFO').upper()))
        
        # Use structured logging if enabled
        if log_config.get('structured', False):
            formatter = StructuredFormatter()
        else:
            format_str = log_config.get('format', 
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            formatter = logging.Formatter(format_str)
        
        handler.setFormatter(formatter)
        self.handlers.append(handler)
    
    def _setup_file_handler(self, log_config: Dict[str, Any]) -> None:
        """Set up file logging handler with rotation."""
        file_config = log_config.get('handlers', {}).get('file', {})
        
        if not file_config.get('enabled', False):
            return
        
        # Create logs directory
        log_file = Path(file_config.get('filename', 'logs/crypto_portfolio.log'))
        log_file.parent.mkdir(exist_ok=True)
        
        # Set up rotating file handler
        max_bytes = file_config.get('max_bytes', 10 * 1024 * 1024)  # 10MB
        backup_count = file_config.get('backup_count', 5)
        
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        
        handler.setLevel(getattr(logging, file_config.get('level', 'DEBUG').upper()))
        
        # Always use structured logging for file output
        formatter = StructuredFormatter()
        handler.setFormatter(formatter)
        
        self.handlers.append(handler)
    
    def _setup_sentry(self, log_config: Dict[str, Any]) -> None:
        """Set up Sentry error reporting."""
        if not SENTRY_AVAILABLE:
            return
        
        sentry_config = log_config.get('handlers', {}).get('sentry', {})
        
        if not sentry_config.get('enabled', False):
            return
        
        dsn = sentry_config.get('dsn')
        if not dsn:
            return
        
        try:
            # Configure Sentry logging integration
            sentry_logging = LoggingIntegration(
                level=getattr(logging, sentry_config.get('level', 'ERROR').upper()),
                event_level=logging.ERROR
            )
            
            # Initialize Sentry
            sentry_sdk.init(
                dsn=dsn,
                environment=sentry_config.get('environment', 'development'),
                integrations=[sentry_logging],
                traces_sample_rate=sentry_config.get('traces_sample_rate', 0.1),
                profiles_sample_rate=sentry_config.get('profiles_sample_rate', 0.1),
                attach_stacktrace=True,
                send_default_pii=False,
            )
            
            self.sentry_initialized = True
            
            # Log successful initialization
            logger = logging.getLogger(__name__)
            logger.info("Sentry error reporting initialized")
            
        except Exception as e:
            # Don't fail if Sentry setup fails
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to initialize Sentry: {e}")
    
    def add_context_to_sentry(self, context: Dict[str, Any]) -> None:
        """Add context information to Sentry scope."""
        if not self.sentry_initialized:
            return
        
        try:
            with sentry_sdk.configure_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
        except Exception:
            # Ignore Sentry context errors
            pass
    
    def capture_exception(self, exception: Exception, extra: Dict[str, Any] = None) -> None:
        """Capture an exception with Sentry."""
        if not self.sentry_initialized:
            return
        
        try:
            with sentry_sdk.configure_scope() as scope:
                if extra:
                    for key, value in extra.items():
                        scope.set_extra(key, value)
                
                sentry_sdk.capture_exception(exception)
        except Exception:
            # Ignore Sentry capture errors
            pass
    
    def capture_message(self, message: str, level: str = 'info', extra: Dict[str, Any] = None) -> None:
        """Capture a message with Sentry."""
        if not self.sentry_initialized:
            return
        
        try:
            with sentry_sdk.configure_scope() as scope:
                if extra:
                    for key, value in extra.items():
                        scope.set_extra(key, value)
                
                sentry_sdk.capture_message(message, level=level)
        except Exception:
            # Ignore Sentry capture errors
            pass


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """Get the global logging manager instance."""
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager


def setup_logging(config: Dict[str, Any] = None) -> None:
    """Set up the global logging system."""
    manager = get_logging_manager()
    if config:
        manager.config = config
    manager.setup_logging()


def capture_exception(exception: Exception, extra: Dict[str, Any] = None) -> None:
    """Capture an exception for error reporting."""
    manager = get_logging_manager()
    manager.capture_exception(exception, extra)


def capture_message(message: str, level: str = 'info', extra: Dict[str, Any] = None) -> None:
    """Capture a message for error reporting."""
    manager = get_logging_manager()
    manager.capture_message(message, level, extra)

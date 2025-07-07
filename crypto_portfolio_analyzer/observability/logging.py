"""Advanced logging system with structured logging and audit trails."""

import logging
import logging.config
import json
import sys
import os
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    # Create a simple fallback for structlog
    class MockStructlog:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)
        @staticmethod
        def configure(**kwargs):
            pass
    structlog = MockStructlog()

try:
    from rich.logging import RichHandler
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    RichHandler = None


@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "structured"  # "structured", "json", "simple"
    output: str = "console"  # "console", "file", "both"
    log_file: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_audit: bool = True
    enable_performance: bool = True
    enable_security: bool = True
    correlation_id: bool = True
    
    def __post_init__(self):
        if self.log_file is None:
            self.log_file = "logs/crypto_portfolio_analyzer.log"


class StructuredLogger:
    """Structured logger with context and correlation tracking."""

    def __init__(self, name: str, config: LogConfig):
        self.name = name
        self.config = config
        if STRUCTLOG_AVAILABLE:
            self.logger = structlog.get_logger(name)
        else:
            self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> 'StructuredLogger':
        """Bind context to logger."""
        new_logger = StructuredLogger(self.name, self.config)
        new_logger._context = {**self._context, **kwargs}
        if STRUCTLOG_AVAILABLE:
            new_logger.logger = self.logger.bind(**new_logger._context)
        else:
            new_logger.logger = self.logger
        return new_logger

    def info(self, message: str, **kwargs):
        """Log info message."""
        if STRUCTLOG_AVAILABLE:
            self.logger.info(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.info(f"{message}{extra_msg}")

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        if STRUCTLOG_AVAILABLE:
            self.logger.debug(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.debug(f"{message}{extra_msg}")

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        if STRUCTLOG_AVAILABLE:
            self.logger.warning(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.warning(f"{message}{extra_msg}")

    def error(self, message: str, **kwargs):
        """Log error message."""
        if STRUCTLOG_AVAILABLE:
            self.logger.error(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.error(f"{message}{extra_msg}")

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        if STRUCTLOG_AVAILABLE:
            self.logger.critical(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.critical(f"{message}{extra_msg}")

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        if STRUCTLOG_AVAILABLE:
            self.logger.exception(message, **kwargs)
        else:
            extra_msg = f" {kwargs}" if kwargs else ""
            self.logger.exception(f"{message}{extra_msg}")


class AuditLogger:
    """Specialized logger for audit trails."""
    
    def __init__(self, config: LogConfig):
        self.config = config
        self.logger = structlog.get_logger("audit")
    
    def log_user_action(self, user_id: str, action: str, resource: str, **kwargs):
        """Log user action for audit trail."""
        self.logger.info(
            "User action",
            user_id=user_id,
            action=action,
            resource=resource,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    def log_system_event(self, event_type: str, component: str, **kwargs):
        """Log system event."""
        self.logger.info(
            "System event",
            event_type=event_type,
            component=component,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    def log_security_event(self, event_type: str, severity: str, **kwargs):
        """Log security-related event."""
        self.logger.warning(
            "Security event",
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    def log_data_access(self, user_id: str, data_type: str, operation: str, **kwargs):
        """Log data access for compliance."""
        self.logger.info(
            "Data access",
            user_id=user_id,
            data_type=data_type,
            operation=operation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )


class PerformanceLogger:
    """Logger for performance metrics and timing."""
    
    def __init__(self, config: LogConfig):
        self.config = config
        self.logger = structlog.get_logger("performance")
    
    def log_request_timing(self, endpoint: str, method: str, duration_ms: float, status_code: int, **kwargs):
        """Log API request timing."""
        self.logger.info(
            "Request timing",
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=status_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    def log_database_query(self, query_type: str, table: str, duration_ms: float, **kwargs):
        """Log database query performance."""
        self.logger.info(
            "Database query",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    def log_external_api_call(self, service: str, endpoint: str, duration_ms: float, success: bool, **kwargs):
        """Log external API call performance."""
        self.logger.info(
            "External API call",
            service=service,
            endpoint=endpoint,
            duration_ms=duration_ms,
            success=success,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )


def setup_logging(config: LogConfig) -> None:
    """Setup comprehensive logging system."""

    # Create logs directory if it doesn't exist
    if config.log_file:
        log_dir = Path(config.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # Configure structlog if available
    if STRUCTLOG_AVAILABLE:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                _get_processor(config.format),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    # Configure standard library logging
    logging_config = _create_logging_config(config)
    logging.config.dictConfig(logging_config)

    # Set root logger level
    logging.getLogger().setLevel(getattr(logging, config.level.upper()))


def _get_processor(format_type: str):
    """Get appropriate log processor based on format."""
    if not STRUCTLOG_AVAILABLE:
        return None

    if format_type == "json":
        return structlog.processors.JSONRenderer()
    elif format_type == "structured":
        return structlog.dev.ConsoleRenderer(colors=True)
    else:
        return structlog.processors.KeyValueRenderer()


def _create_logging_config(config: LogConfig) -> Dict[str, Any]:
    """Create logging configuration dictionary."""
    
    formatters = {
        "structured": {
            "format": "%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        },
        "simple": {
            "format": "%(levelname)s: %(message)s"
        }
    }
    
    handlers = {}
    
    # Console handler
    if config.output in ["console", "both"]:
        if config.format == "structured" and RICH_AVAILABLE:
            handlers["console"] = {
                "class": "rich.logging.RichHandler",
                "level": config.level,
                "formatter": "structured",
                "show_time": True,
                "show_level": True,
                "show_path": True,
                "markup": True,
                "rich_tracebacks": True
            }
        else:
            handlers["console"] = {
                "class": "logging.StreamHandler",
                "level": config.level,
                "formatter": config.format,
                "stream": "ext://sys.stdout"
            }
    
    # File handler
    if config.output in ["file", "both"] and config.log_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": config.level,
            "formatter": "json",
            "filename": config.log_file,
            "maxBytes": config.max_file_size,
            "backupCount": config.backup_count,
            "encoding": "utf-8"
        }
    
    # Audit handler
    if config.enable_audit:
        audit_file = str(Path(config.log_file).parent / "audit.log") if config.log_file else "logs/audit.log"
        handlers["audit"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "json",
            "filename": audit_file,
            "maxBytes": config.max_file_size,
            "backupCount": config.backup_count,
            "encoding": "utf-8"
        }
    
    # Performance handler
    if config.enable_performance:
        perf_file = str(Path(config.log_file).parent / "performance.log") if config.log_file else "logs/performance.log"
        handlers["performance"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "json",
            "filename": perf_file,
            "maxBytes": config.max_file_size,
            "backupCount": config.backup_count,
            "encoding": "utf-8"
        }
    
    # Security handler
    if config.enable_security:
        security_file = str(Path(config.log_file).parent / "security.log") if config.log_file else "logs/security.log"
        handlers["security"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "WARNING",
            "formatter": "json",
            "filename": security_file,
            "maxBytes": config.max_file_size,
            "backupCount": config.backup_count,
            "encoding": "utf-8"
        }
    
    # Root logger configuration
    root_handlers = list(handlers.keys())
    if "audit" in root_handlers:
        root_handlers.remove("audit")
    if "performance" in root_handlers:
        root_handlers.remove("performance")
    if "security" in root_handlers:
        root_handlers.remove("security")
    
    loggers = {
        "": {
            "level": config.level,
            "handlers": root_handlers
        }
    }
    
    # Specialized loggers
    if config.enable_audit:
        loggers["audit"] = {
            "level": "INFO",
            "handlers": ["audit"],
            "propagate": False
        }
    
    if config.enable_performance:
        loggers["performance"] = {
            "level": "INFO",
            "handlers": ["performance"],
            "propagate": False
        }
    
    if config.enable_security:
        loggers["security"] = {
            "level": "WARNING",
            "handlers": ["security"],
            "propagate": False
        }
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers
    }


def get_logger(name: str, config: Optional[LogConfig] = None) -> StructuredLogger:
    """Get a structured logger instance."""
    if config is None:
        config = LogConfig()
    
    return StructuredLogger(name, config)


# Global logger instances
_audit_logger: Optional[AuditLogger] = None
_performance_logger: Optional[PerformanceLogger] = None


def get_audit_logger(config: Optional[LogConfig] = None) -> AuditLogger:
    """Get audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        if config is None:
            config = LogConfig()
        _audit_logger = AuditLogger(config)
    return _audit_logger


def get_performance_logger(config: Optional[LogConfig] = None) -> PerformanceLogger:
    """Get performance logger instance."""
    global _performance_logger
    if _performance_logger is None:
        if config is None:
            config = LogConfig()
        _performance_logger = PerformanceLogger(config)
    return _performance_logger

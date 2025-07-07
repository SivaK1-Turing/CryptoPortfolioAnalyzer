"""Observability module for monitoring, logging, and metrics."""

from .logging import (
    setup_logging,
    get_logger,
    LogConfig,
    StructuredLogger,
    AuditLogger
)

from .metrics import (
    MetricsCollector,
    PrometheusMetrics,
    CustomMetrics,
    MetricType,
    MetricDefinition,
    register_metric,
    increment_counter,
    set_gauge,
    record_histogram,
    record_timer
)

from .monitoring import (
    HealthChecker,
    HealthCheck,
    SystemMonitor,
    ApplicationMonitor,
    PerformanceMonitor,
    MonitoringDashboard,
    get_health_checker,
    get_system_monitor,
    get_app_monitor,
    get_performance_monitor
)

from .tracing import (
    TracingConfig,
    RequestTracer,
    DistributedTracer,
    trace_function,
    trace_async_function
)

from .alerts import (
    AlertManager,
    AlertRule,
    AlertChannel,
    AlertSeverity,
    send_alert,
    setup_alerting
)

__all__ = [
    # Logging
    'setup_logging',
    'get_logger',
    'LogConfig',
    'StructuredLogger',
    'AuditLogger',
    
    # Metrics
    'MetricsCollector',
    'PrometheusMetrics',
    'CustomMetrics',
    'MetricType',
    'MetricDefinition',
    'register_metric',
    'increment_counter',
    'set_gauge',
    'record_histogram',
    'record_timer',
    
    # Monitoring
    'HealthChecker',
    'HealthCheck',
    'SystemMonitor',
    'ApplicationMonitor',
    'PerformanceMonitor',
    'MonitoringDashboard',
    'get_health_checker',
    'get_system_monitor',
    'get_app_monitor',
    'get_performance_monitor',
    
    # Tracing
    'TracingConfig',
    'RequestTracer',
    'DistributedTracer',
    'trace_function',
    'trace_async_function',
    
    # Alerts
    'AlertManager',
    'AlertRule',
    'AlertChannel',
    'AlertSeverity',
    'send_alert',
    'setup_alerting'
]

"""Performance monitoring and health checks for real-time streaming system."""

import asyncio
import logging
import psutil
import time
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from collections import deque, defaultdict
import statistics

from .events import StreamEvent, EventType, StreamEventBus

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """Types of performance metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }


@dataclass
class SystemHealth:
    """System health information."""
    status: HealthStatus
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_connections: int
    uptime_seconds: float
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "disk_usage": self.disk_usage,
            "network_connections": self.network_connections,
            "uptime_seconds": self.uptime_seconds,
            "last_check": self.last_check.isoformat(),
            "issues": self.issues
        }


@dataclass
class ConnectionHealth:
    """Connection health information."""
    connection_id: str
    status: HealthStatus
    connected: bool
    last_message_time: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    latency_ms: Optional[float] = None
    reconnect_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_id": self.connection_id,
            "status": self.status.value,
            "connected": self.connected,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "latency_ms": self.latency_ms,
            "reconnect_count": self.reconnect_count
        }


class MetricsCollector:
    """Collects and aggregates performance metrics."""
    
    def __init__(self, retention_hours: int = 24):
        """Initialize metrics collector.
        
        Args:
            retention_hours: How long to retain metrics
        """
        self.retention_hours = retention_hours
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start metrics collector."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Metrics collector started")
    
    async def stop(self):
        """Stop metrics collector."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Metrics collector stopped")
    
    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric."""
        self.metrics[metric.name].append(metric)
        
        # Update aggregated values
        if metric.metric_type == MetricType.COUNTER:
            self.counters[metric.name] += metric.value
        elif metric.metric_type == MetricType.GAUGE:
            self.gauges[metric.name] = metric.value
        elif metric.metric_type == MetricType.HISTOGRAM:
            self.histograms[metric.name].append(metric.value)
            # Keep only recent values
            if len(self.histograms[metric.name]) > 1000:
                self.histograms[metric.name] = self.histograms[metric.name][-1000:]
        elif metric.metric_type == MetricType.TIMER:
            self.timers[metric.name].append(metric.value)
            # Keep only recent values
            if len(self.timers[metric.name]) > 1000:
                self.timers[metric.name] = self.timers[metric.name][-1000:]
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            metric_type=MetricType.COUNTER,
            tags=tags or {}
        )
        self.record_metric(metric)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            tags=tags or {}
        )
        self.record_metric(metric)
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            metric_type=MetricType.HISTOGRAM,
            tags=tags or {}
        )
        self.record_metric(metric)
    
    def record_timer(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timer value."""
        metric = PerformanceMetric(
            name=name,
            value=duration_ms,
            metric_type=MetricType.TIMER,
            tags=tags or {}
        )
        self.record_metric(metric)
    
    def get_counter_value(self, name: str) -> float:
        """Get current counter value."""
        return self.counters.get(name, 0.0)
    
    def get_gauge_value(self, name: str) -> Optional[float]:
        """Get current gauge value."""
        return self.gauges.get(name)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics."""
        values = self.histograms.get(name, [])
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99)
        }
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics."""
        values = self.timers.get(name, [])
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min_ms": min(values),
            "max_ms": max(values),
            "mean_ms": statistics.mean(values),
            "median_ms": statistics.median(values),
            "p95_ms": self._percentile(values, 95),
            "p99_ms": self._percentile(values, 99)
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {name: self.get_histogram_stats(name) for name in self.histograms},
            "timers": {name: self.get_timer_stats(name) for name in self.timers}
        }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100.0) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    async def _cleanup_loop(self):
        """Cleanup old metrics."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
                
                # Clean up old metrics
                for metric_name, metric_deque in self.metrics.items():
                    # Remove old metrics
                    while metric_deque and metric_deque[0].timestamp < cutoff_time:
                        metric_deque.popleft()
                
                logger.debug("Cleaned up old metrics")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics cleanup: {e}")


class HealthChecker:
    """System health monitoring."""
    
    def __init__(self, check_interval: float = 30.0):
        """Initialize health checker.
        
        Args:
            check_interval: Health check interval in seconds
        """
        self.check_interval = check_interval
        self.system_start_time = time.time()
        self.connection_health: Dict[str, ConnectionHealth] = {}
        self.health_handlers: Set[Callable[[SystemHealth], None]] = set()
        
        # Health check task
        self._health_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start health checker."""
        if self._running:
            return
        
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health checker started")
    
    async def stop(self):
        """Stop health checker."""
        if not self._running:
            return
        
        self._running = False
        
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health checker stopped")
    
    def add_health_handler(self, handler: Callable[[SystemHealth], None]):
        """Add health status handler."""
        self.health_handlers.add(handler)
    
    def remove_health_handler(self, handler: Callable[[SystemHealth], None]):
        """Remove health status handler."""
        self.health_handlers.discard(handler)
    
    def update_connection_health(self, connection_id: str, health: ConnectionHealth):
        """Update connection health status."""
        self.connection_health[connection_id] = health
    
    def get_system_health(self) -> SystemHealth:
        """Get current system health."""
        try:
            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network_connections = len(psutil.net_connections())
            uptime = time.time() - self.system_start_time
            
            # Determine overall health status
            issues = []
            status = HealthStatus.HEALTHY
            
            if cpu_usage > 90:
                issues.append(f"High CPU usage: {cpu_usage:.1f}%")
                status = HealthStatus.CRITICAL
            elif cpu_usage > 70:
                issues.append(f"Elevated CPU usage: {cpu_usage:.1f}%")
                status = HealthStatus.WARNING
            
            if memory.percent > 90:
                issues.append(f"High memory usage: {memory.percent:.1f}%")
                status = HealthStatus.CRITICAL
            elif memory.percent > 70:
                issues.append(f"Elevated memory usage: {memory.percent:.1f}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            if disk.percent > 95:
                issues.append(f"High disk usage: {disk.percent:.1f}%")
                status = HealthStatus.CRITICAL
            elif disk.percent > 85:
                issues.append(f"Elevated disk usage: {disk.percent:.1f}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            # Check connection health
            unhealthy_connections = [
                conn_id for conn_id, health in self.connection_health.items()
                if health.status != HealthStatus.HEALTHY
            ]
            
            if unhealthy_connections:
                issues.append(f"Unhealthy connections: {len(unhealthy_connections)}")
                if len(unhealthy_connections) > len(self.connection_health) / 2:
                    status = HealthStatus.CRITICAL
                elif status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
            
            return SystemHealth(
                status=status,
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_connections=network_connections,
                uptime_seconds=uptime,
                issues=issues
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return SystemHealth(
                status=HealthStatus.UNKNOWN,
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                network_connections=0,
                uptime_seconds=0.0,
                issues=[f"Health check error: {str(e)}"]
            )
    
    async def _health_check_loop(self):
        """Health check loop."""
        while self._running:
            try:
                health = self.get_system_health()
                
                # Notify handlers
                for handler in self.health_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            asyncio.create_task(handler(health))
                        else:
                            handler(health)
                    except Exception as e:
                        logger.error(f"Error in health handler: {e}")
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.check_interval)


class PerformanceMonitor:
    """Comprehensive performance monitoring service."""

    def __init__(self, metrics_retention_hours: int = 24, health_check_interval: float = 30.0):
        """Initialize performance monitor.

        Args:
            metrics_retention_hours: How long to retain metrics
            health_check_interval: Health check interval in seconds
        """
        self.metrics_collector = MetricsCollector(metrics_retention_hours)
        self.health_checker = HealthChecker(health_check_interval)
        self.event_bus = StreamEventBus()

        # Performance tracking
        self.start_time = datetime.now(timezone.utc)
        self.operation_timers: Dict[str, float] = {}

        # Setup health handler
        self.health_checker.add_health_handler(self._handle_health_update)

    async def start(self):
        """Start performance monitoring."""
        await self.metrics_collector.start()
        await self.health_checker.start()
        logger.info("Performance monitor started")

    async def stop(self):
        """Stop performance monitoring."""
        await self.metrics_collector.stop()
        await self.health_checker.stop()
        logger.info("Performance monitor stopped")

    # Metrics recording methods
    def record_price_update(self, symbol: str, processing_time_ms: float):
        """Record price update metrics."""
        self.metrics_collector.increment_counter("price_updates_total", tags={"symbol": symbol})
        self.metrics_collector.record_timer("price_update_processing_time", processing_time_ms, tags={"symbol": symbol})

    def record_portfolio_update(self, processing_time_ms: float):
        """Record portfolio update metrics."""
        self.metrics_collector.increment_counter("portfolio_updates_total")
        self.metrics_collector.record_timer("portfolio_update_processing_time", processing_time_ms)

    def record_alert_triggered(self, alert_type: str):
        """Record alert metrics."""
        self.metrics_collector.increment_counter("alerts_triggered_total", tags={"type": alert_type})

    def record_websocket_connection(self, connected: bool):
        """Record WebSocket connection metrics."""
        if connected:
            self.metrics_collector.increment_counter("websocket_connections_total")
        else:
            self.metrics_collector.increment_counter("websocket_disconnections_total")

    def record_api_request(self, endpoint: str, status_code: int, response_time_ms: float):
        """Record API request metrics."""
        self.metrics_collector.increment_counter(
            "api_requests_total",
            tags={"endpoint": endpoint, "status": str(status_code)}
        )
        self.metrics_collector.record_timer(
            "api_response_time",
            response_time_ms,
            tags={"endpoint": endpoint}
        )

    def record_error(self, error_type: str, component: str):
        """Record error metrics."""
        self.metrics_collector.increment_counter(
            "errors_total",
            tags={"type": error_type, "component": component}
        )

    def set_active_connections(self, count: int):
        """Set active connections gauge."""
        self.metrics_collector.set_gauge("active_connections", count)

    def set_queue_size(self, queue_name: str, size: int):
        """Set queue size gauge."""
        self.metrics_collector.set_gauge("queue_size", size, tags={"queue": queue_name})

    # Timer context managers
    def timer(self, operation_name: str):
        """Context manager for timing operations."""
        return OperationTimer(self, operation_name)

    def start_timer(self, operation_name: str):
        """Start timing an operation."""
        self.operation_timers[operation_name] = time.time()

    def end_timer(self, operation_name: str) -> float:
        """End timing an operation and record the duration."""
        if operation_name not in self.operation_timers:
            return 0.0

        start_time = self.operation_timers.pop(operation_name)
        duration_ms = (time.time() - start_time) * 1000
        self.metrics_collector.record_timer(f"{operation_name}_duration", duration_ms)
        return duration_ms

    # Health monitoring
    def update_connection_health(self, connection_id: str, health: ConnectionHealth):
        """Update connection health."""
        self.health_checker.update_connection_health(connection_id, health)

    def get_system_health(self) -> SystemHealth:
        """Get current system health."""
        return self.health_checker.get_system_health()

    # Metrics retrieval
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        health = self.get_system_health()
        metrics = self.metrics_collector.get_all_metrics()

        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return {
            "uptime_seconds": uptime,
            "system_health": health.to_dict(),
            "metrics": metrics,
            "connection_health": {
                conn_id: health.to_dict()
                for conn_id, health in self.health_checker.connection_health.items()
            }
        }

    async def _handle_health_update(self, health: SystemHealth):
        """Handle health status updates."""
        # Record health metrics
        self.metrics_collector.set_gauge("cpu_usage_percent", health.cpu_usage)
        self.metrics_collector.set_gauge("memory_usage_percent", health.memory_usage)
        self.metrics_collector.set_gauge("disk_usage_percent", health.disk_usage)
        self.metrics_collector.set_gauge("network_connections", health.network_connections)

        # Broadcast health event
        event = StreamEvent(
            event_type=EventType.SYSTEM_STATUS,
            data=health.to_dict(),
            source="performance_monitor"
        )
        await self.event_bus.publish(event)

        # Log critical health issues
        if health.status == HealthStatus.CRITICAL:
            logger.critical(f"System health critical: {', '.join(health.issues)}")
        elif health.status == HealthStatus.WARNING:
            logger.warning(f"System health warning: {', '.join(health.issues)}")


class OperationTimer:
    """Context manager for timing operations."""

    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.monitor.metrics_collector.record_timer(
                f"{self.operation_name}_duration",
                duration_ms
            )

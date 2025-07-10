"""Metrics collection and monitoring system with Prometheus integration."""

import time
import threading
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from collections import defaultdict, deque
import json

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
        start_http_server, push_to_gateway
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for type hints when Prometheus is not available
    class CollectorRegistry:
        pass
    class Counter:
        pass
    class Gauge:
        pass
    class Histogram:
        pass
    class Summary:
        pass
    class Info:
        pass


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"


@dataclass
class MetricDefinition:
    """Metric definition."""
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms
    
    def __post_init__(self):
        if self.metric_type == MetricType.HISTOGRAM and self.buckets is None:
            self.buckets = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]


class CustomMetrics:
    """Custom metrics collector for when Prometheus is not available."""
    
    def __init__(self):
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.summaries: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.info: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment counter metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set gauge metric value."""
        key = self._make_key(name, labels)
        with self._lock:
            self.gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe histogram metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self.histograms[key].append(value)
    
    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe summary metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self.summaries[key].append(value)
    
    def set_info(self, name: str, info_dict: Dict[str, str], labels: Optional[Dict[str, str]] = None):
        """Set info metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self.info[key] = info_dict
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as dictionary."""
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": {k: list(v) for k, v in self.histograms.items()},
                "summaries": {k: list(v) for k, v in self.summaries.items()},
                "info": dict(self.info)
            }
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class PrometheusMetrics:
    """Prometheus metrics collector."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("prometheus_client is required for PrometheusMetrics")
        
        self.registry = registry or CollectorRegistry()
        self.metrics: Dict[str, Any] = {}
    
    def register_metric(self, definition: MetricDefinition) -> Any:
        """Register a new metric."""
        if definition.name in self.metrics:
            return self.metrics[definition.name]
        
        kwargs = {
            "name": definition.name,
            "documentation": definition.description,
            "labelnames": definition.labels,
            "registry": self.registry
        }
        
        if definition.metric_type == MetricType.COUNTER:
            metric = Counter(**kwargs)
        elif definition.metric_type == MetricType.GAUGE:
            metric = Gauge(**kwargs)
        elif definition.metric_type == MetricType.HISTOGRAM:
            kwargs["buckets"] = definition.buckets
            metric = Histogram(**kwargs)
        elif definition.metric_type == MetricType.SUMMARY:
            metric = Summary(**kwargs)
        elif definition.metric_type == MetricType.INFO:
            metric = Info(**kwargs)
        else:
            raise ValueError(f"Unknown metric type: {definition.metric_type}")
        
        self.metrics[definition.name] = metric
        return metric
    
    def get_metric(self, name: str) -> Optional[Any]:
        """Get registered metric by name."""
        return self.metrics.get(name)
    
    def generate_metrics(self) -> str:
        """Generate Prometheus metrics output."""
        return generate_latest(self.registry).decode('utf-8')


class MetricsCollector:
    """Main metrics collector that abstracts Prometheus vs custom metrics."""
    
    def __init__(self, use_prometheus: bool = True, registry: Optional[CollectorRegistry] = None):
        self.use_prometheus = use_prometheus and PROMETHEUS_AVAILABLE
        
        if self.use_prometheus:
            self.prometheus = PrometheusMetrics(registry)
            self.custom = None
        else:
            self.prometheus = None
            self.custom = CustomMetrics()
        
        self.definitions: Dict[str, MetricDefinition] = {}
        self._setup_default_metrics()
    
    def _setup_default_metrics(self):
        """Setup default application metrics."""
        default_metrics = [
            MetricDefinition(
                name="app_requests_total",
                metric_type=MetricType.COUNTER,
                description="Total number of requests",
                labels=["method", "endpoint", "status"]
            ),
            MetricDefinition(
                name="app_request_duration_seconds",
                metric_type=MetricType.HISTOGRAM,
                description="Request duration in seconds",
                labels=["method", "endpoint"]
            ),
            MetricDefinition(
                name="app_active_connections",
                metric_type=MetricType.GAUGE,
                description="Number of active connections"
            ),
            MetricDefinition(
                name="portfolio_value_usd",
                metric_type=MetricType.GAUGE,
                description="Current portfolio value in USD",
                labels=["portfolio_id"]
            ),
            MetricDefinition(
                name="price_updates_total",
                metric_type=MetricType.COUNTER,
                description="Total number of price updates",
                labels=["symbol", "source"]
            ),
            MetricDefinition(
                name="api_calls_total",
                metric_type=MetricType.COUNTER,
                description="Total number of external API calls",
                labels=["service", "endpoint", "status"]
            ),
            MetricDefinition(
                name="errors_total",
                metric_type=MetricType.COUNTER,
                description="Total number of errors",
                labels=["component", "error_type"]
            ),
            MetricDefinition(
                name="system_cpu_usage",
                metric_type=MetricType.GAUGE,
                description="System CPU usage percentage"
            ),
            MetricDefinition(
                name="system_memory_usage",
                metric_type=MetricType.GAUGE,
                description="System memory usage percentage"
            )
        ]
        
        for definition in default_metrics:
            self.register_metric(definition)
    
    def register_metric(self, definition: MetricDefinition):
        """Register a new metric definition."""
        self.definitions[definition.name] = definition
        
        if self.use_prometheus:
            self.prometheus.register_metric(definition)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment counter metric."""
        if self.use_prometheus:
            metric = self.prometheus.get_metric(name)
            if metric:
                if labels:
                    metric.labels(**labels).inc(value)
                else:
                    metric.inc(value)
        else:
            self.custom.increment_counter(name, value, labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set gauge metric value."""
        if self.use_prometheus:
            metric = self.prometheus.get_metric(name)
            if metric:
                if labels:
                    metric.labels(**labels).set(value)
                else:
                    metric.set(value)
        else:
            self.custom.set_gauge(name, value, labels)
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe histogram metric."""
        if self.use_prometheus:
            metric = self.prometheus.get_metric(name)
            if metric:
                if labels:
                    metric.labels(**labels).observe(value)
                else:
                    metric.observe(value)
        else:
            self.custom.observe_histogram(name, value, labels)
    
    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe summary metric."""
        if self.use_prometheus:
            metric = self.prometheus.get_metric(name)
            if metric:
                if labels:
                    metric.labels(**labels).observe(value)
                else:
                    metric.observe(value)
        else:
            self.custom.observe_summary(name, value, labels)
    
    def set_info(self, name: str, info_dict: Dict[str, str], labels: Optional[Dict[str, str]] = None):
        """Set info metric."""
        if self.use_prometheus:
            metric = self.prometheus.get_metric(name)
            if metric:
                if labels:
                    metric.labels(**labels).info(info_dict)
                else:
                    metric.info(info_dict)
        else:
            self.custom.set_info(name, info_dict, labels)
    
    def get_metrics(self) -> Union[str, Dict[str, Any]]:
        """Get metrics in appropriate format."""
        if self.use_prometheus:
            return self.prometheus.generate_metrics()
        else:
            return self.custom.get_metrics()
    
    def start_http_server(self, port: int = 8000):
        """Start HTTP server for metrics (Prometheus only)."""
        if self.use_prometheus:
            start_http_server(port, registry=self.prometheus.registry)
        else:
            raise NotImplementedError("HTTP server only available with Prometheus")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def register_metric(definition: MetricDefinition):
    """Register a metric with the global collector."""
    get_metrics_collector().register_metric(definition)


def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
    """Increment counter metric."""
    get_metrics_collector().increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Set gauge metric value."""
    get_metrics_collector().set_gauge(name, value, labels)


def record_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record histogram observation."""
    get_metrics_collector().observe_histogram(name, value, labels)


def record_timer(name: str, duration_seconds: float, labels: Optional[Dict[str, str]] = None):
    """Record timer metric."""
    get_metrics_collector().observe_histogram(name, duration_seconds, labels)


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            record_timer(self.metric_name, duration, self.labels)


def timer(metric_name: str, labels: Optional[Dict[str, str]] = None) -> TimerContext:
    """Create timer context manager."""
    return TimerContext(metric_name, labels)

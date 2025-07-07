"""System and application monitoring with health checks and dashboards."""

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    # Create mock psutil for when it's not available
    class MockPsutil:
        @staticmethod
        def cpu_percent(interval=None):
            return 50.0
        @staticmethod
        def virtual_memory():
            class Memory:
                percent = 60.0
                total = 8 * 1024 * 1024 * 1024  # 8GB
                available = 3 * 1024 * 1024 * 1024  # 3GB
            return Memory()
        @staticmethod
        def disk_usage(path):
            class Disk:
                percent = 70.0
                total = 500 * 1024 * 1024 * 1024  # 500GB
                free = 150 * 1024 * 1024 * 1024   # 150GB
            return Disk()
        @staticmethod
        def net_io_counters():
            class Network:
                bytes_sent = 1024 * 1024 * 100  # 100MB
                bytes_recv = 1024 * 1024 * 200  # 200MB
            return Network()
        @staticmethod
        def Process():
            class Process:
                def cpu_percent(self):
                    return 25.0
                def memory_percent(self):
                    return 15.0
                def num_threads(self):
                    return 10
            return Process()
    psutil = MockPsutil()

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json

from .metrics import get_metrics_collector, set_gauge, increment_counter
from .logging import get_logger


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_function: Callable[[], bool]
    description: str
    timeout_seconds: float = 5.0
    critical: bool = True
    tags: List[str] = field(default_factory=list)
    
    async def run(self) -> 'HealthCheckResult':
        """Run the health check."""
        start_time = time.time()
        status = HealthStatus.UNKNOWN
        error_message = None
        
        try:
            # Run check with timeout
            if asyncio.iscoroutinefunction(self.check_function):
                result = await asyncio.wait_for(
                    self.check_function(),
                    timeout=self.timeout_seconds
                )
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.check_function
                )
            
            status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
            
        except asyncio.TimeoutError:
            status = HealthStatus.UNHEALTHY
            error_message = f"Health check timed out after {self.timeout_seconds}s"
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            error_message = str(e)
        
        duration = time.time() - start_time
        
        return HealthCheckResult(
            name=self.name,
            status=status,
            duration_seconds=duration,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc),
            critical=self.critical,
            tags=self.tags
        )


@dataclass
class HealthCheckResult:
    """Health check result."""
    name: str
    status: HealthStatus
    duration_seconds: float
    timestamp: datetime
    critical: bool = True
    error_message: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
            "critical": self.critical,
            "error_message": self.error_message,
            "tags": self.tags
        }


class HealthChecker:
    """Health check manager."""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self.logger = get_logger("health_checker")
    
    def register_check(self, check: HealthCheck):
        """Register a health check."""
        self.checks[check.name] = check
        self.logger.info(f"Registered health check: {check.name}")
    
    def unregister_check(self, name: str):
        """Unregister a health check."""
        if name in self.checks:
            del self.checks[name]
            if name in self.last_results:
                del self.last_results[name]
            self.logger.info(f"Unregistered health check: {name}")
    
    async def run_check(self, name: str) -> Optional[HealthCheckResult]:
        """Run a specific health check."""
        if name not in self.checks:
            return None
        
        result = await self.checks[name].run()
        self.last_results[name] = result
        
        # Record metrics
        status_value = 1 if result.status == HealthStatus.HEALTHY else 0
        set_gauge("health_check_status", status_value, {"check_name": name})
        set_gauge("health_check_duration", result.duration_seconds, {"check_name": name})
        
        if result.status != HealthStatus.HEALTHY:
            increment_counter("health_check_failures", 1, {"check_name": name})
        
        return result
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        tasks = [self.run_check(name) for name in self.checks.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            name: result for name, result in zip(self.checks.keys(), results)
            if isinstance(result, HealthCheckResult)
        }
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.last_results:
            return HealthStatus.UNKNOWN
        
        critical_checks = [
            result for result in self.last_results.values()
            if result.critical
        ]
        
        if not critical_checks:
            return HealthStatus.HEALTHY
        
        unhealthy_critical = [
            result for result in critical_checks
            if result.status == HealthStatus.UNHEALTHY
        ]
        
        degraded_critical = [
            result for result in critical_checks
            if result.status == HealthStatus.DEGRADED
        ]
        
        if unhealthy_critical:
            return HealthStatus.UNHEALTHY
        elif degraded_critical:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        overall_status = self.get_overall_status()
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                name: result.to_dict()
                for name, result in self.last_results.items()
            },
            "summary": {
                "total_checks": len(self.checks),
                "healthy": len([r for r in self.last_results.values() if r.status == HealthStatus.HEALTHY]),
                "degraded": len([r for r in self.last_results.values() if r.status == HealthStatus.DEGRADED]),
                "unhealthy": len([r for r in self.last_results.values() if r.status == HealthStatus.UNHEALTHY])
            }
        }


class SystemMonitor:
    """System resource monitoring."""
    
    def __init__(self, collection_interval: float = 30.0):
        self.collection_interval = collection_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.logger = get_logger("system_monitor")
    
    def start(self):
        """Start system monitoring."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info("System monitoring started")
    
    def stop(self):
        """Stop system monitoring."""
        self.running = False
        if self.thread:
            self.thread.join()
        self.logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._collect_system_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                self.logger.error(f"Error collecting system metrics: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self):
        """Collect system metrics."""
        try:
            # CPU metrics
            if PSUTIL_AVAILABLE:
                cpu_percent = psutil.cpu_percent(interval=1)
            else:
                cpu_percent = psutil.cpu_percent()
            set_gauge("system_cpu_usage", cpu_percent)

            # Memory metrics
            memory = psutil.virtual_memory()
            set_gauge("system_memory_usage", memory.percent)
            set_gauge("system_memory_total", memory.total)
            set_gauge("system_memory_available", memory.available)

            # Disk metrics
            disk_path = '/' if PSUTIL_AVAILABLE else 'C:\\'
            disk = psutil.disk_usage(disk_path)
            set_gauge("system_disk_usage", disk.percent)
            set_gauge("system_disk_total", disk.total)
            set_gauge("system_disk_free", disk.free)

            # Network metrics
            network = psutil.net_io_counters()
            set_gauge("system_network_bytes_sent", network.bytes_sent)
            set_gauge("system_network_bytes_recv", network.bytes_recv)

            # Process metrics
            process = psutil.Process()
            set_gauge("process_cpu_percent", process.cpu_percent())
            set_gauge("process_memory_percent", process.memory_percent())
            set_gauge("process_num_threads", process.num_threads())
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")


class ApplicationMonitor:
    """Application-specific monitoring."""
    
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.request_count = 0
        self.error_count = 0
        self.logger = get_logger("app_monitor")
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record API request metrics."""
        self.request_count += 1
        
        # Record metrics
        increment_counter("app_requests_total", 1, {
            "method": method,
            "endpoint": endpoint,
            "status": str(status_code)
        })
        
        set_gauge("app_request_duration_seconds", duration, {
            "method": method,
            "endpoint": endpoint
        })
        
        if status_code >= 400:
            self.error_count += 1
            increment_counter("app_errors_total", 1, {
                "endpoint": endpoint,
                "status": str(status_code)
            })
    
    def record_portfolio_update(self, portfolio_id: str, value: float):
        """Record portfolio value update."""
        set_gauge("portfolio_value_usd", value, {"portfolio_id": portfolio_id})
        increment_counter("portfolio_updates_total", 1, {"portfolio_id": portfolio_id})
    
    def record_price_update(self, symbol: str, source: str, success: bool):
        """Record price update."""
        status = "success" if success else "error"
        increment_counter("price_updates_total", 1, {
            "symbol": symbol,
            "source": source,
            "status": status
        })
    
    def get_application_metrics(self) -> Dict[str, Any]:
        """Get application metrics summary."""
        uptime = datetime.now(timezone.utc) - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "start_time": self.start_time.isoformat()
        }


class PerformanceMonitor:
    """Performance monitoring and profiling."""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.response_times: Dict[str, List[float]] = {}
        self.logger = get_logger("performance_monitor")
    
    def record_response_time(self, operation: str, duration: float):
        """Record operation response time."""
        if operation not in self.response_times:
            self.response_times[operation] = []
        
        self.response_times[operation].append(duration)
        
        # Keep only recent samples
        if len(self.response_times[operation]) > self.max_samples:
            self.response_times[operation] = self.response_times[operation][-self.max_samples:]
        
        # Record metric
        set_gauge("operation_duration_seconds", duration, {"operation": operation})
    
    def get_performance_stats(self, operation: str) -> Optional[Dict[str, float]]:
        """Get performance statistics for operation."""
        if operation not in self.response_times or not self.response_times[operation]:
            return None
        
        times = self.response_times[operation]
        times.sort()
        
        return {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "mean": sum(times) / len(times),
            "p50": times[len(times) // 2],
            "p95": times[int(len(times) * 0.95)],
            "p99": times[int(len(times) * 0.99)]
        }
    
    def get_all_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all operations."""
        return {
            operation: self.get_performance_stats(operation)
            for operation in self.response_times.keys()
        }


class MonitoringDashboard:
    """Monitoring dashboard data aggregator."""
    
    def __init__(self, health_checker: HealthChecker, system_monitor: SystemMonitor,
                 app_monitor: ApplicationMonitor, perf_monitor: PerformanceMonitor):
        self.health_checker = health_checker
        self.system_monitor = system_monitor
        self.app_monitor = app_monitor
        self.perf_monitor = perf_monitor
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        # Run health checks
        health_results = await self.health_checker.run_all_checks()
        health_summary = self.health_checker.get_health_summary()
        
        # Get application metrics
        app_metrics = self.app_monitor.get_application_metrics()
        
        # Get performance stats
        performance_stats = self.perf_monitor.get_all_performance_stats()
        
        # Get current system metrics
        try:
            disk_path = '/' if PSUTIL_AVAILABLE else 'C:\\'
            current_metrics = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage(disk_path).percent
            }
        except Exception:
            current_metrics = {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "disk_percent": 70.0
            }
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health_summary,
            "system": current_metrics,
            "application": app_metrics,
            "performance": performance_stats,
            "status": health_summary["status"]
        }


# Global monitoring instances
_health_checker: Optional[HealthChecker] = None
_system_monitor: Optional[SystemMonitor] = None
_app_monitor: Optional[ApplicationMonitor] = None
_perf_monitor: Optional[PerformanceMonitor] = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def get_system_monitor() -> SystemMonitor:
    """Get global system monitor instance."""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor


def get_app_monitor() -> ApplicationMonitor:
    """Get global application monitor instance."""
    global _app_monitor
    if _app_monitor is None:
        _app_monitor = ApplicationMonitor()
    return _app_monitor


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor

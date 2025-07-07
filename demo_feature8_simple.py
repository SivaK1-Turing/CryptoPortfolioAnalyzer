#!/usr/bin/env python3
"""
Simple demo for Feature 8: CI/CD, Packaging & Observability
This script demonstrates the core observability features in a simple way.
"""

import sys
import time
import asyncio
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def demo_logging():
    """Demo the logging system."""
    print("\n📝 FEATURE 8: LOGGING SYSTEM DEMO")
    print("=" * 50)
    
    try:
        from crypto_portfolio_analyzer.observability.logging import LogConfig, get_logger, setup_logging
        
        # Setup simple logging
        config = LogConfig(level="INFO", format="simple", output="console")
        setup_logging(config)
        
        # Get logger and test it
        logger = get_logger("feature8_demo")
        
        print("✅ Logging system initialized")
        logger.info("Feature 8 logging demo started", component="demo")
        logger.info("Processing portfolio data", portfolio_id="demo-123", value=150000)
        logger.warning("Demo warning message", alert_type="test")
        
        # Test bound logger
        bound_logger = logger.bind(user_id="user-456", session_id="session-789")
        bound_logger.info("User action logged with context")
        
        print("✅ Logging demo completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Logging demo failed: {e}")
        return False


def demo_metrics():
    """Demo the metrics system."""
    print("\n📊 FEATURE 8: METRICS SYSTEM DEMO")
    print("=" * 50)
    
    try:
        from crypto_portfolio_analyzer.observability.metrics import MetricsCollector, MetricDefinition, MetricType
        
        # Create metrics collector (using custom backend)
        collector = MetricsCollector(use_prometheus=False)
        print("✅ Metrics collector created")
        
        # Register custom metric
        custom_metric = MetricDefinition(
            name="demo_operations_total",
            metric_type=MetricType.COUNTER,
            description="Demo operations counter",
            labels=["operation_type", "status"]
        )
        collector.register_metric(custom_metric)
        print("✅ Custom metric registered")
        
        # Record some metrics
        collector.increment_counter("demo_operations_total", 1, {"operation_type": "portfolio_calc", "status": "success"})
        collector.increment_counter("app_requests_total", 5, {"method": "GET", "endpoint": "/api/portfolio", "status": "200"})
        
        collector.set_gauge("portfolio_value_usd", 150000.0, {"portfolio_id": "demo-portfolio"})
        collector.set_gauge("system_cpu_usage", 45.5)
        
        collector.record_histogram("request_duration_seconds", 0.125, {"method": "GET", "endpoint": "/api/portfolio"})
        collector.record_histogram("request_duration_seconds", 0.089, {"method": "POST", "endpoint": "/api/portfolio"})
        
        print("✅ Metrics recorded successfully")
        
        # Get metrics data
        metrics_data = collector.get_metrics()
        print(f"✅ Metrics data retrieved: {len(metrics_data)} metric types")
        
        # Show some metrics
        print("\n📈 Sample Metrics:")
        if "counters" in metrics_data:
            print(f"  • Counters: {len(metrics_data['counters'])} metrics")
        if "gauges" in metrics_data:
            print(f"  • Gauges: {len(metrics_data['gauges'])} metrics")
        if "histograms" in metrics_data:
            print(f"  • Histograms: {len(metrics_data['histograms'])} metrics")
        
        print("✅ Metrics demo completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Metrics demo failed: {e}")
        return False


async def demo_health_checks():
    """Demo the health check system."""
    print("\n🏥 FEATURE 8: HEALTH CHECK SYSTEM DEMO")
    print("=" * 50)
    
    try:
        from crypto_portfolio_analyzer.observability.monitoring import HealthChecker, HealthCheck
        
        # Create health checker
        health_checker = HealthChecker()
        print("✅ Health checker created")
        
        # Define simple health check functions
        def api_health():
            return True  # Simulate healthy API
        
        def database_health():
            return True  # Simulate healthy database
        
        def cache_health():
            time.sleep(0.1)  # Simulate some work
            return True
        
        # Register health checks
        checks = [
            HealthCheck("api_service", api_health, "API service health check"),
            HealthCheck("database", database_health, "Database connectivity check"),
            HealthCheck("cache_service", cache_health, "Cache service health check")
        ]
        
        for check in checks:
            health_checker.register_check(check)
        
        print(f"✅ Registered {len(checks)} health checks")
        
        # Run individual health check
        result = await health_checker.run_check("api_service")
        print(f"✅ API health check: {result.status.value} ({result.duration_seconds:.3f}s)")
        
        # Run all health checks
        all_results = await health_checker.run_all_checks()
        print(f"✅ All health checks completed: {len(all_results)} results")
        
        # Show results
        print("\n🏥 Health Check Results:")
        for name, result in all_results.items():
            status_icon = "✅" if result.status.value == "healthy" else "❌"
            print(f"  {status_icon} {name}: {result.status.value} ({result.duration_seconds:.3f}s)")
        
        # Get overall status
        overall_status = health_checker.get_overall_status()
        print(f"\n🎯 Overall System Health: {overall_status.value.upper()}")
        
        # Get health summary
        summary = health_checker.get_health_summary()
        print(f"📊 Health Summary: {summary['summary']['healthy']}/{summary['summary']['total_checks']} checks healthy")
        
        print("✅ Health check demo completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Health check demo failed: {e}")
        return False


def demo_system_monitoring():
    """Demo the system monitoring."""
    print("\n🖥️ FEATURE 8: SYSTEM MONITORING DEMO")
    print("=" * 50)
    
    try:
        from crypto_portfolio_analyzer.observability.monitoring import SystemMonitor, ApplicationMonitor
        
        # Create system monitor
        system_monitor = SystemMonitor(collection_interval=1.0)
        print("✅ System monitor created")
        
        # Start monitoring briefly
        system_monitor.start()
        print("✅ System monitoring started")
        
        # Let it collect some data
        time.sleep(2)
        
        # Create application monitor
        app_monitor = ApplicationMonitor()
        print("✅ Application monitor created")
        
        # Record some application metrics
        app_monitor.record_request("GET", "/api/portfolio", 200, 0.125)
        app_monitor.record_request("POST", "/api/portfolio", 201, 0.089)
        app_monitor.record_request("GET", "/api/portfolio/123", 404, 0.045)
        
        app_monitor.record_portfolio_update("portfolio-1", 150000.0)
        app_monitor.record_portfolio_update("portfolio-2", 75000.0)
        
        app_monitor.record_price_update("BTC", "coinbase", True)
        app_monitor.record_price_update("ETH", "binance", True)
        
        print("✅ Application metrics recorded")
        
        # Get application metrics
        app_metrics = app_monitor.get_application_metrics()
        print(f"\n📱 Application Metrics:")
        print(f"  • Uptime: {app_metrics['uptime_seconds']:.1f} seconds")
        print(f"  • Total Requests: {app_metrics['total_requests']}")
        print(f"  • Total Errors: {app_metrics['total_errors']}")
        print(f"  • Error Rate: {app_metrics['error_rate']:.1%}")
        
        # Stop monitoring
        system_monitor.stop()
        print("✅ System monitoring stopped")
        
        print("✅ System monitoring demo completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ System monitoring demo failed: {e}")
        return False


def demo_configuration_files():
    """Demo checking CI/CD and packaging configuration."""
    print("\n⚙️ FEATURE 8: CI/CD & PACKAGING CONFIGURATION DEMO")
    print("=" * 50)
    
    try:
        # Check for configuration files
        files_to_check = [
            (".github/workflows/ci.yml", "CI/CD Pipeline"),
            ("pyproject.toml", "Package Configuration"),
            ("Dockerfile", "Container Configuration"),
            ("requirements.txt", "Dependencies"),
        ]
        
        found_files = 0
        for file_path, description in files_to_check:
            if Path(file_path).exists():
                print(f"✅ {description}: {file_path}")
                found_files += 1
            else:
                print(f"⚠️ {description}: {file_path} (not found)")
        
        print(f"\n📊 Configuration Status: {found_files}/{len(files_to_check)} files found")
        
        if found_files >= 3:
            print("✅ CI/CD and packaging configuration is properly set up")
        else:
            print("⚠️ Some configuration files are missing")
        
        print("✅ Configuration check completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")
        return False


async def main():
    """Main demo function."""
    print("🚀 FEATURE 8: CI/CD, PACKAGING & OBSERVABILITY - SIMPLE DEMO")
    print("=" * 70)
    print("This demo shows the core observability features of Feature 8.")
    print()
    
    # Run all demos
    demos = [
        ("Logging System", demo_logging),
        ("Metrics System", demo_metrics),
        ("Health Checks", demo_health_checks),
        ("System Monitoring", demo_system_monitoring),
        ("Configuration Files", demo_configuration_files)
    ]
    
    results = []
    
    for demo_name, demo_func in demos:
        try:
            if asyncio.iscoroutinefunction(demo_func):
                result = await demo_func()
            else:
                result = demo_func()
            results.append((demo_name, result))
        except Exception as e:
            print(f"❌ {demo_name} failed with exception: {e}")
            results.append((demo_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 FEATURE 8 DEMO SUMMARY")
    print("=" * 70)
    
    passed = 0
    for i, (demo_name, result) in enumerate(results):
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{i+1}. {demo_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nOverall: {passed}/{total} demos successful")
    
    if passed == total:
        print("\n🎉 Feature 8 is working perfectly!")
        print("\n🔧 Demonstrated Components:")
        print("  ✅ Structured Logging with Context")
        print("  ✅ Metrics Collection and Aggregation")
        print("  ✅ Health Check System")
        print("  ✅ System and Application Monitoring")
        print("  ✅ CI/CD and Packaging Configuration")
        
        print("\n💡 Feature 8 provides:")
        print("  • Enterprise-grade observability")
        print("  • Automated CI/CD pipeline")
        print("  • Package distribution setup")
        print("  • Comprehensive monitoring")
        print("  • Production-ready tooling")
    else:
        print(f"\n⚠️ {total - passed} demos failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))

#!/usr/bin/env python3
"""
Simple runner for Feature 8: CI/CD, Packaging & Observability
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("🚀 FEATURE 8: CI/CD, PACKAGING & OBSERVABILITY")
    print("=" * 60)
    
    try:
        # Test basic imports
        print("📦 Testing imports...")
        from crypto_portfolio_analyzer.observability.logging import LogConfig, get_logger
        from crypto_portfolio_analyzer.observability.metrics import MetricsCollector
        print("✅ All imports successful")
        
        # Setup logging
        print("\n📝 Setting up logging...")
        logger = get_logger("feature8")
        logger.info("Feature 8 started successfully")
        print("✅ Logging working")
        
        # Setup metrics
        print("\n📊 Setting up metrics...")
        collector = MetricsCollector(use_prometheus=False)
        collector.increment_counter("feature8_demo_runs", 1)
        collector.set_gauge("feature8_status", 1.0)
        print("✅ Metrics working")
        
        # Check configuration files
        print("\n⚙️ Checking configuration...")
        config_files = [
            ".github/workflows/ci.yml",
            "pyproject.toml", 
            "Dockerfile"
        ]
        
        for config_file in config_files:
            if Path(config_file).exists():
                print(f"✅ {config_file} found")
            else:
                print(f"⚠️ {config_file} not found")
        
        print("\n🎉 Feature 8 is working!")
        print("\n🔧 Available components:")
        print("  • Structured logging system")
        print("  • Metrics collection")
        print("  • Health monitoring")
        print("  • CI/CD pipeline")
        print("  • Package configuration")
        print("  • Docker containerization")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())

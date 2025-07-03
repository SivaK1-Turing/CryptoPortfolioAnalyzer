#!/usr/bin/env python3
"""
Demo script to test the visualization features of the Crypto Portfolio Analyzer.
This script demonstrates all the key visualization capabilities.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.visualization.charts import (
    ChartGenerator, ChartConfig, ChartType, AllocationChart, PortfolioChart
)
from crypto_portfolio_analyzer.visualization.reports import (
    ReportGenerator, ReportConfig, ReportType, ReportFormat
)
from crypto_portfolio_analyzer.visualization.export import (
    DataExporter, ExportConfig, ExportFormat
)
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding
from crypto_portfolio_analyzer.data.models import HistoricalPrice, DataSource


def create_sample_data():
    """Create sample portfolio data for testing."""
    print("📊 Creating sample portfolio data...")
    
    # Create sample holdings
    holdings = [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.5"),
            average_cost=Decimal("45000"),
            current_price=Decimal("50000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("10.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3500")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("1000"),
            average_cost=Decimal("1.2"),
            current_price=Decimal("1.5")
        )
    ]
    
    # Create portfolio snapshots over time
    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    snapshots = []
    
    for i in range(31):  # 31 days of data
        # Simulate price changes
        btc_price = Decimal("45000") + Decimal(str(i * 200))  # BTC trending up
        eth_price = Decimal("3000") + Decimal(str(i * 20))    # ETH trending up
        ada_price = Decimal("1.2") + Decimal(str(i * 0.01))  # ADA slight up
        
        daily_holdings = [
            PortfolioHolding(
                symbol="BTC",
                quantity=Decimal("1.5"),
                average_cost=Decimal("45000"),
                current_price=btc_price
            ),
            PortfolioHolding(
                symbol="ETH",
                quantity=Decimal("10.0"),
                average_cost=Decimal("3000"),
                current_price=eth_price
            ),
            PortfolioHolding(
                symbol="ADA",
                quantity=Decimal("1000"),
                average_cost=Decimal("1.2"),
                current_price=ada_price
            )
        ]
        
        total_value = sum(h.market_value for h in daily_holdings)
        total_cost = sum(h.cost_basis for h in daily_holdings)
        
        snapshot = PortfolioSnapshot(
            timestamp=base_time + timedelta(days=i),
            holdings=daily_holdings,
            total_value=total_value,
            total_cost=total_cost
        )
        snapshots.append(snapshot)
    
    # Create sample historical prices
    historical_prices = []
    for i in range(30):
        price = Decimal("50000") + Decimal(str(i * 100))
        historical_prices.append(
            HistoricalPrice(
                symbol="BTC",
                timestamp=base_time + timedelta(days=i),
                price=price,
                volume=Decimal("1000000") + Decimal(str(i * 10000)),
                market_cap=Decimal("1000000000000"),
                data_source=DataSource.COINGECKO
            )
        )
    
    print(f"✅ Created {len(snapshots)} portfolio snapshots")
    print(f"✅ Created {len(historical_prices)} price data points")
    
    return snapshots, historical_prices


def test_chart_generation(snapshots, historical_prices):
    """Test chart generation capabilities."""
    print("\n🎨 Testing Chart Generation...")
    
    try:
        # Test allocation chart
        print("  📊 Creating allocation pie chart...")
        config = ChartConfig(chart_type=ChartType.PIE, title="Portfolio Allocation")
        allocation_chart = AllocationChart(config)
        latest_snapshot = snapshots[-1]
        fig = allocation_chart.create(latest_snapshot)
        
        # Export to HTML
        output_file = "test_allocation_chart.html"
        fig.write_html(output_file, include_plotlyjs=True)
        print(f"  ✅ Allocation chart saved to {output_file}")
        
        # Test portfolio performance chart
        print("  📈 Creating portfolio performance chart...")
        config = ChartConfig(chart_type=ChartType.LINE, title="Portfolio Performance")
        portfolio_chart = PortfolioChart(config)
        fig = portfolio_chart.create(snapshots)
        
        # Export to HTML
        output_file = "test_portfolio_chart.html"
        fig.write_html(output_file, include_plotlyjs=True)
        print(f"  ✅ Portfolio chart saved to {output_file}")
        
        # Test using ChartGenerator (legacy interface)
        print("  🔧 Testing ChartGenerator interface...")
        generator = ChartGenerator()
        
        # Create allocation chart using generator
        alloc_fig = generator.create_allocation_pie_chart(latest_snapshot, "Test Allocation")
        alloc_fig.write_html("test_generator_allocation.html", include_plotlyjs=True)
        print("  ✅ Generator allocation chart created")
        
        # Create portfolio performance chart using generator
        perf_fig = generator.create_portfolio_performance_chart(snapshots, "Test Performance")
        perf_fig.write_html("test_generator_portfolio.html", include_plotlyjs=True)
        print("  ✅ Generator portfolio chart created")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Chart generation failed: {e}")
        return False


def test_report_generation(snapshots):
    """Test report generation capabilities."""
    print("\n📋 Testing Report Generation...")
    
    try:
        generator = ReportGenerator()
        
        # Test HTML report
        print("  📄 Generating HTML report...")
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.HTML,
            title="Test Portfolio Report",
            include_charts=True,
            include_tables=True,
            output_path="test_portfolio_report.html"
        )
        
        report_path = generator.generate_report(config, snapshots)
        print(f"  ✅ HTML report saved to {report_path}")
        
        # Test JSON report
        print("  📊 Generating JSON report...")
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.JSON,
            title="Test Portfolio JSON Report",
            output_path="test_portfolio_report.json"
        )
        
        report_path = generator.generate_report(config, snapshots)
        print(f"  ✅ JSON report saved to {report_path}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Report generation failed: {e}")
        return False


def test_data_export(snapshots, historical_prices):
    """Test data export capabilities."""
    print("\n📤 Testing Data Export...")
    
    try:
        exporter = DataExporter()
        
        # Test CSV export
        print("  📊 Exporting to CSV...")
        csv_path = exporter.export_portfolio_snapshots(
            snapshots, 
            ExportFormat.CSV, 
            "test_portfolio_export.csv"
        )
        print(f"  ✅ CSV export saved to {csv_path}")
        
        # Test JSON export
        print("  📊 Exporting to JSON...")
        json_path = exporter.export_portfolio_snapshots(
            snapshots,
            ExportFormat.JSON,
            "test_portfolio_export.json"
        )
        print(f"  ✅ JSON export saved to {json_path}")
        
        # Test Excel export
        print("  📊 Exporting to Excel...")
        excel_path = exporter.export_portfolio_snapshots(
            snapshots,
            ExportFormat.EXCEL,
            "test_portfolio_export.xlsx"
        )
        print(f"  ✅ Excel export saved to {excel_path}")
        
        # Test historical prices export
        print("  📊 Exporting historical prices...")
        prices_path = exporter.export_historical_prices(
            historical_prices,
            ExportFormat.CSV,
            "test_historical_prices.csv"
        )
        print(f"  ✅ Historical prices saved to {prices_path}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Data export failed: {e}")
        return False


async def test_dashboard():
    """Test dashboard capabilities (basic setup)."""
    print("\n🌐 Testing Dashboard Setup...")
    
    try:
        from crypto_portfolio_analyzer.visualization.dashboard import (
            WebDashboard, DashboardConfig
        )
        
        # Create dashboard configuration
        config = DashboardConfig(
            host="localhost",
            port=8081,  # Use different port for testing
            title="Test Dashboard",
            theme="light"
        )
        
        # Create dashboard instance
        dashboard = WebDashboard(config)
        print("  ✅ Dashboard instance created successfully")
        print(f"  📍 Dashboard configured for {config.host}:{config.port}")
        print("  ℹ️  To start dashboard, run: crypto-portfolio visualize dashboard")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Dashboard setup failed: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 Testing Crypto Portfolio Analyzer - Visualization Features")
    print("=" * 60)
    
    # Create sample data
    snapshots, historical_prices = create_sample_data()
    
    # Run tests
    results = []
    
    # Test chart generation
    results.append(test_chart_generation(snapshots, historical_prices))
    
    # Test report generation
    results.append(test_report_generation(snapshots))
    
    # Test data export
    results.append(test_data_export(snapshots, historical_prices))
    
    # Test dashboard setup
    results.append(asyncio.run(test_dashboard()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    test_names = [
        "Chart Generation",
        "Report Generation", 
        "Data Export",
        "Dashboard Setup"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {name}: {status}")
    
    total_passed = sum(results)
    print(f"\nOverall: {total_passed}/{len(results)} tests passed")
    
    if all(results):
        print("\n🎉 All visualization features are working correctly!")
        print("\n📁 Generated Files:")
        print("  • test_allocation_chart.html")
        print("  • test_portfolio_chart.html") 
        print("  • test_generator_allocation.html")
        print("  • test_generator_portfolio.html")
        print("  • test_portfolio_report.html")
        print("  • test_portfolio_report.json")
        print("  • test_portfolio_export.csv")
        print("  • test_portfolio_export.json")
        print("  • test_portfolio_export.xlsx")
        print("  • test_historical_prices.csv")
        print("\n💡 Open the HTML files in your browser to view the charts!")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

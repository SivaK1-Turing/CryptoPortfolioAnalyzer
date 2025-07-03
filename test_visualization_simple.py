#!/usr/bin/env python3
"""
Simple demo script to test the core visualization features without PDF dependencies.
This script demonstrates the key visualization capabilities that work on Windows.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.visualization.charts import (
    ChartGenerator, ChartConfig, ChartType, AllocationChart, PortfolioChart
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
    
    print(f"✅ Created {len(snapshots)} portfolio snapshots")
    print(f"💰 Latest portfolio value: ${snapshots[-1].total_value:,.2f}")
    print(f"📈 Total return: ${snapshots[-1].total_value - snapshots[-1].total_cost:,.2f}")
    
    return snapshots


def test_chart_generation(snapshots):
    """Test chart generation capabilities."""
    print("\n🎨 Testing Chart Generation...")
    
    try:
        latest_snapshot = snapshots[-1]
        
        # Test 1: Allocation Chart using new chart system
        print("  📊 Creating allocation pie chart...")
        config = ChartConfig(chart_type=ChartType.PIE, title="Portfolio Allocation")
        allocation_chart = AllocationChart(config)
        fig = allocation_chart.create(latest_snapshot)
        
        # Export to HTML
        output_file = "test_allocation_chart.html"
        fig.write_html(output_file, include_plotlyjs=True)
        print(f"  ✅ Allocation chart saved to {output_file}")
        
        # Test 2: Portfolio Performance Chart using new chart system
        print("  📈 Creating portfolio performance chart...")
        config = ChartConfig(chart_type=ChartType.LINE, title="Portfolio Performance Over Time")
        portfolio_chart = PortfolioChart(config)
        fig = portfolio_chart.create(snapshots)
        
        # Export to HTML
        output_file = "test_portfolio_performance.html"
        fig.write_html(output_file, include_plotlyjs=True)
        print(f"  ✅ Portfolio performance chart saved to {output_file}")
        
        # Test 3: Using ChartGenerator (legacy interface)
        print("  🔧 Testing ChartGenerator interface...")
        generator = ChartGenerator()
        
        # Create allocation chart using generator
        alloc_fig = generator.create_allocation_pie_chart(latest_snapshot, "Portfolio Allocation (Generator)")
        alloc_fig.write_html("test_generator_allocation.html", include_plotlyjs=True)
        print("  ✅ Generator allocation chart created")
        
        # Create portfolio performance chart using generator
        perf_fig = generator.create_portfolio_performance_chart(snapshots, "Portfolio Performance (Generator)")
        perf_fig.write_html("test_generator_portfolio.html", include_plotlyjs=True)
        print("  ✅ Generator portfolio chart created")
        
        # Test 4: Chart configuration and themes
        print("  🎨 Testing chart themes...")
        config_dark = ChartConfig(
            chart_type=ChartType.PIE, 
            title="Portfolio Allocation (Dark Theme)",
            theme="plotly_dark"
        )
        dark_chart = AllocationChart(config_dark)
        dark_fig = dark_chart.create(latest_snapshot)
        dark_fig.write_html("test_dark_theme_chart.html", include_plotlyjs=True)
        print("  ✅ Dark theme chart created")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Chart generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_export_simple(snapshots):
    """Test basic data export capabilities (without Excel)."""
    print("\n📤 Testing Data Export...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import (
            DataExporter, ExportFormat
        )
        
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
        
        return True
        
    except Exception as e:
        print(f"  ❌ Data export failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chart_data_analysis(snapshots):
    """Test chart data and analysis."""
    print("\n📊 Testing Chart Data Analysis...")
    
    try:
        latest_snapshot = snapshots[-1]
        
        # Analyze portfolio composition
        print("  📈 Portfolio Analysis:")
        total_value = float(latest_snapshot.total_value)
        
        for holding in latest_snapshot.holdings:
            allocation_pct = (float(holding.market_value) / total_value) * 100
            pnl = holding.market_value - holding.cost_basis
            pnl_pct = (float(pnl) / float(holding.cost_basis)) * 100
            
            print(f"    • {holding.symbol}: ${holding.market_value:,.2f} ({allocation_pct:.1f}%) - P&L: ${pnl:,.2f} ({pnl_pct:+.1f}%)")
        
        # Performance over time
        print("  📊 Performance Analysis:")
        initial_value = float(snapshots[0].total_value)
        final_value = float(snapshots[-1].total_value)
        total_return = ((final_value - initial_value) / initial_value) * 100
        
        print(f"    • Initial Value: ${initial_value:,.2f}")
        print(f"    • Final Value: ${final_value:,.2f}")
        print(f"    • Total Return: {total_return:+.2f}%")
        print(f"    • Period: {len(snapshots)} days")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Data analysis failed: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 Testing Crypto Portfolio Analyzer - Visualization Features (Simple)")
    print("=" * 70)
    
    # Create sample data
    snapshots = create_sample_data()
    
    # Run tests
    results = []
    
    # Test chart generation
    results.append(test_chart_generation(snapshots))
    
    # Test data export (simple)
    results.append(test_data_export_simple(snapshots))
    
    # Test data analysis
    results.append(test_chart_data_analysis(snapshots))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    test_names = [
        "Chart Generation",
        "Data Export (CSV/JSON)", 
        "Data Analysis"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {name}: {status}")
    
    total_passed = sum(results)
    print(f"\nOverall: {total_passed}/{len(results)} tests passed")
    
    if all(results):
        print("\n🎉 Core visualization features are working correctly!")
        print("\n📁 Generated Files:")
        print("  • test_allocation_chart.html - Portfolio allocation pie chart")
        print("  • test_portfolio_performance.html - Portfolio performance over time") 
        print("  • test_generator_allocation.html - Allocation chart (via generator)")
        print("  • test_generator_portfolio.html - Performance chart (via generator)")
        print("  • test_dark_theme_chart.html - Dark theme example")
        print("  • test_portfolio_export.csv - Portfolio data in CSV format")
        print("  • test_portfolio_export.json - Portfolio data in JSON format")
        print("\n💡 Next Steps:")
        print("  1. Open the HTML files in your browser to view the interactive charts")
        print("  2. Try the CLI commands: crypto-portfolio visualize --help")
        print("  3. Test the dashboard: crypto-portfolio visualize dashboard")
        print("  4. Generate reports: crypto-portfolio visualize report")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

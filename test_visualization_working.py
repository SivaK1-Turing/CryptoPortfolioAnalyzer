#!/usr/bin/env python3
"""
Working demo of the visualization features that are confirmed to work.
This focuses on the core functionality that's been tested and verified.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.visualization.charts import (
    ChartConfig, ChartType, AllocationChart, PortfolioChart
)
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding


def create_sample_portfolio():
    """Create a realistic sample portfolio."""
    print("📊 Creating sample portfolio...")
    
    # Create holdings with realistic crypto data
    holdings = [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("0.5"),
            average_cost=Decimal("45000"),
            current_price=Decimal("52000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("5.0"),
            average_cost=Decimal("3200"),
            current_price=Decimal("3800")
        ),
        PortfolioHolding(
            symbol="SOL",
            quantity=Decimal("20.0"),
            average_cost=Decimal("80"),
            current_price=Decimal("95")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("2000"),
            average_cost=Decimal("0.8"),
            current_price=Decimal("1.2")
        )
    ]
    
    # Calculate totals
    total_value = sum(h.market_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=holdings,
        total_value=total_value,
        total_cost=total_cost
    )
    
    print(f"✅ Portfolio created with {len(holdings)} holdings")
    print(f"💰 Total value: ${total_value:,.2f}")
    print(f"📈 Total P&L: ${total_value - total_cost:,.2f}")
    
    return snapshot


def create_historical_snapshots():
    """Create historical portfolio snapshots for performance tracking."""
    print("📈 Creating historical performance data...")
    
    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    snapshots = []
    
    # Simulate 30 days of portfolio performance
    for day in range(31):
        # Simulate price movements (generally upward trend with volatility)
        btc_price = Decimal("45000") + Decimal(str(day * 150)) + Decimal(str((day % 7) * 500))
        eth_price = Decimal("3200") + Decimal(str(day * 15)) + Decimal(str((day % 5) * 50))
        sol_price = Decimal("80") + Decimal(str(day * 0.5)) + Decimal(str((day % 3) * 5))
        ada_price = Decimal("0.8") + Decimal(str(day * 0.01)) + Decimal(str((day % 4) * 0.05))
        
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                quantity=Decimal("0.5"),
                average_cost=Decimal("45000"),
                current_price=btc_price
            ),
            PortfolioHolding(
                symbol="ETH",
                quantity=Decimal("5.0"),
                average_cost=Decimal("3200"),
                current_price=eth_price
            ),
            PortfolioHolding(
                symbol="SOL",
                quantity=Decimal("20.0"),
                average_cost=Decimal("80"),
                current_price=sol_price
            ),
            PortfolioHolding(
                symbol="ADA",
                quantity=Decimal("2000"),
                average_cost=Decimal("0.8"),
                current_price=ada_price
            )
        ]
        
        total_value = sum(h.market_value for h in holdings)
        total_cost = sum(h.cost_basis for h in holdings)
        
        snapshot = PortfolioSnapshot(
            timestamp=base_time + timedelta(days=day),
            holdings=holdings,
            total_value=total_value,
            total_cost=total_cost
        )
        snapshots.append(snapshot)
    
    print(f"✅ Created {len(snapshots)} historical snapshots")
    return snapshots


def test_allocation_chart(snapshot):
    """Test portfolio allocation pie chart."""
    print("\n🥧 Testing Allocation Pie Chart...")
    
    try:
        # Create chart configuration
        config = ChartConfig(
            chart_type=ChartType.PIE,
            title="Portfolio Allocation",
            width=800,
            height=600,
            theme="plotly_white"
        )
        
        # Create chart
        chart = AllocationChart(config)
        figure = chart.create(snapshot)
        
        # Save to file
        output_file = "portfolio_allocation.html"
        figure.write_html(output_file, include_plotlyjs=True)
        
        print(f"✅ Allocation chart saved to {output_file}")
        print(f"📊 Chart contains {len(figure.data[0].labels)} assets")
        
        # Print allocation breakdown
        print("📈 Allocation breakdown:")
        total_value = float(snapshot.total_value)
        for holding in snapshot.holdings:
            allocation = (float(holding.market_value) / total_value) * 100
            print(f"  • {holding.symbol}: {allocation:.1f}% (${holding.market_value:,.2f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Allocation chart failed: {e}")
        return False


def test_performance_chart(snapshots):
    """Test portfolio performance chart."""
    print("\n📈 Testing Performance Chart...")
    
    try:
        # Create chart configuration
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title="Portfolio Performance Over Time",
            width=1000,
            height=600,
            theme="plotly_white"
        )
        
        # Create chart
        chart = PortfolioChart(config)
        figure = chart.create(snapshots)
        
        # Save to file
        output_file = "portfolio_performance.html"
        figure.write_html(output_file, include_plotlyjs=True)
        
        print(f"✅ Performance chart saved to {output_file}")
        print(f"📊 Chart contains {len(figure.data)} data series")
        
        # Print performance summary
        initial_value = float(snapshots[0].total_value)
        final_value = float(snapshots[-1].total_value)
        total_return = ((final_value - initial_value) / initial_value) * 100
        
        print("📊 Performance summary:")
        print(f"  • Period: {len(snapshots)} days")
        print(f"  • Initial value: ${initial_value:,.2f}")
        print(f"  • Final value: ${final_value:,.2f}")
        print(f"  • Total return: {total_return:+.2f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance chart failed: {e}")
        return False


def test_dark_theme_chart(snapshot):
    """Test dark theme chart."""
    print("\n🌙 Testing Dark Theme Chart...")
    
    try:
        # Create dark theme configuration
        config = ChartConfig(
            chart_type=ChartType.PIE,
            title="Portfolio Allocation (Dark Theme)",
            width=800,
            height=600,
            theme="plotly_dark"
        )
        
        # Create chart
        chart = AllocationChart(config)
        figure = chart.create(snapshot)
        
        # Save to file
        output_file = "portfolio_allocation_dark.html"
        figure.write_html(output_file, include_plotlyjs=True)
        
        print(f"✅ Dark theme chart saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Dark theme chart failed: {e}")
        return False


def test_csv_export(snapshots):
    """Test CSV export functionality."""
    print("\n📄 Testing CSV Export...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import (
            DataExporter, ExportFormat
        )
        
        exporter = DataExporter()
        csv_path = exporter.export_portfolio_snapshots(
            snapshots,
            ExportFormat.CSV,
            "portfolio_data.csv"
        )
        
        print(f"✅ CSV export saved to {csv_path}")
        
        # Read and show first few lines
        with open(csv_path, 'r') as f:
            lines = f.readlines()[:3]  # Header + 2 data rows
            print("📄 CSV preview:")
            for line in lines:
                print(f"  {line.strip()}")
        
        return True
        
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        return False


def main():
    """Main demonstration function."""
    print("🚀 Crypto Portfolio Analyzer - Visualization Demo")
    print("=" * 60)
    
    # Create sample data
    current_snapshot = create_sample_portfolio()
    historical_snapshots = create_historical_snapshots()
    
    # Run tests
    tests = [
        ("Allocation Chart", lambda: test_allocation_chart(current_snapshot)),
        ("Performance Chart", lambda: test_performance_chart(historical_snapshots)),
        ("Dark Theme Chart", lambda: test_dark_theme_chart(current_snapshot)),
        ("CSV Export", lambda: test_csv_export(historical_snapshots))
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        results.append(test_func())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DEMO SUMMARY")
    print("=" * 60)
    
    for i, (test_name, result) in enumerate(zip([t[0] for t in tests], results)):
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{i+1}. {test_name}: {status}")
    
    passed = sum(results)
    total = len(results)
    print(f"\nOverall: {passed}/{total} features working")
    
    if passed > 0:
        print("\n🎉 Visualization features are working!")
        print("\n📁 Generated Files:")
        if results[0]: print("  • portfolio_allocation.html - Interactive pie chart")
        if results[1]: print("  • portfolio_performance.html - Performance over time")
        if results[2]: print("  • portfolio_allocation_dark.html - Dark theme example")
        if results[3]: print("  • portfolio_data.csv - Exported portfolio data")
        
        print("\n💡 How to view:")
        print("  1. Open the .html files in your web browser")
        print("  2. The charts are fully interactive (zoom, hover, etc.)")
        print("  3. Open the .csv file in Excel or any spreadsheet app")
        
        print("\n🔧 Next Steps:")
        print("  • Try the CLI: crypto-portfolio visualize --help")
        print("  • Test with real data from your portfolio")
        print("  • Customize chart themes and layouts")
    
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    exit(main())

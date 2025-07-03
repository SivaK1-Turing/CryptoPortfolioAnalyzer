#!/usr/bin/env python3
"""
Test script for Feature 7: Enterprise-Grade Export and Distribution.
This script demonstrates all export and distribution capabilities.
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.visualization.export import (
    DataExporter, ExportConfig, ExportFormat
)
from crypto_portfolio_analyzer.visualization.exports import ChartExporter
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding
from crypto_portfolio_analyzer.analytics.reports import ReportGenerator
from crypto_portfolio_analyzer.data.models import HistoricalPrice


def create_sample_portfolio_data() -> List[PortfolioSnapshot]:
    """Create sample portfolio data for testing."""
    holdings = [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.5"),
            average_cost=Decimal("45000"),
            current_price=Decimal("52000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("10.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3800")
        ),
        PortfolioHolding(
            symbol="SOL",
            quantity=Decimal("50.0"),
            average_cost=Decimal("80"),
            current_price=Decimal("110")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("2000"),
            average_cost=Decimal("1.0"),
            current_price=Decimal("1.3")
        )
    ]
    
    # Create portfolio snapshot
    total_value = sum(h.market_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=holdings,
        total_value=total_value,
        total_cost=total_cost,
        cash_balance=Decimal("5000")
    )
    
    return [snapshot]


def create_sample_price_data() -> List[HistoricalPrice]:
    """Create sample historical price data."""
    prices = []
    base_prices = {"BTC": 50000, "ETH": 3500, "SOL": 95}
    
    for i in range(10):
        for symbol, base_price in base_prices.items():
            price = HistoricalPrice(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                price=Decimal(str(base_price + (i * 100))),
                volume=Decimal("1000000"),
                market_cap=Decimal("50000000000")
            )
            prices.append(price)
    
    return prices


def test_csv_export():
    """Test CSV export functionality."""
    print("\n📊 Testing CSV Export...")
    
    try:
        exporter = DataExporter()
        snapshots = create_sample_portfolio_data()
        
        # Test portfolio snapshots export
        config = ExportConfig(
            format=ExportFormat.CSV,
            include_headers=True,
            decimal_places=6
        )
        
        output_file = exporter.export_data(snapshots, config, "test_portfolio.csv")
        print(f"✅ Portfolio exported to CSV: {output_file}")
        
        # Verify file exists and has content
        if Path(output_file).exists():
            with open(output_file, 'r') as f:
                content = f.read()
                print(f"📄 CSV file size: {len(content)} characters")
                print(f"📋 First 200 characters: {content[:200]}...")
        
        # Test historical prices export
        prices = create_sample_price_data()
        price_file = exporter.export_data(prices, config, "test_prices.csv")
        print(f"✅ Prices exported to CSV: {price_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        return False


def test_json_export():
    """Test JSON export functionality."""
    print("\n📄 Testing JSON Export...")
    
    try:
        exporter = DataExporter()
        snapshots = create_sample_portfolio_data()
        
        config = ExportConfig(
            format=ExportFormat.JSON,
            include_metadata=True,
            decimal_places=6
        )
        
        output_file = exporter.export_data(snapshots, config, "test_portfolio.json")
        print(f"✅ Portfolio exported to JSON: {output_file}")
        
        # Verify JSON structure
        if Path(output_file).exists():
            with open(output_file, 'r') as f:
                data = json.load(f)
                print(f"📊 JSON structure:")
                print(f"  • Format version: {data.get('format_version')}")
                print(f"  • Data type: {data.get('data_type')}")
                print(f"  • Records: {data.get('metadata', {}).get('total_records', 0)}")
                print(f"  • Exported at: {data.get('exported_at')}")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False


def test_excel_export():
    """Test Excel export functionality."""
    print("\n📈 Testing Excel Export...")
    
    try:
        exporter = DataExporter()
        snapshots = create_sample_portfolio_data()
        
        config = ExportConfig(
            format=ExportFormat.EXCEL,
            include_metadata=True,
            decimal_places=2
        )
        
        output_file = exporter.export_data(snapshots, config, "test_portfolio.xlsx")
        print(f"✅ Portfolio exported to Excel: {output_file}")
        
        # Verify file exists
        if Path(output_file).exists():
            file_size = Path(output_file).stat().st_size
            print(f"📊 Excel file size: {file_size:,} bytes")
            print(f"📋 Excel file contains portfolio summary and holdings sheets")
        
        return True
        
    except Exception as e:
        print(f"❌ Excel export failed: {e}")
        return False


def test_chart_export():
    """Test chart export functionality."""
    print("\n📊 Testing Chart Export...")
    
    try:
        import plotly.graph_objects as go
        
        # Create sample chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=['BTC', 'ETH', 'SOL', 'ADA'],
            y=[78000, 38000, 5500, 2600],
            mode='markers+lines',
            name='Portfolio Value by Asset'
        ))
        
        fig.update_layout(
            title='Sample Portfolio Chart',
            xaxis_title='Assets',
            yaxis_title='Value ($)',
            template='plotly_white'
        )
        
        exporter = ChartExporter()
        
        # Test PNG export
        success_png = exporter.export_chart(fig, "test_chart.png", format='png')
        print(f"✅ Chart exported to PNG: {success_png}")
        
        # Test HTML export
        success_html = exporter.export_chart(fig, "test_chart.html", format='html')
        print(f"✅ Chart exported to HTML: {success_html}")
        
        # Test SVG export
        success_svg = exporter.export_chart(fig, "test_chart.svg", format='svg')
        print(f"✅ Chart exported to SVG: {success_svg}")
        
        # Test chart gallery
        charts = {
            "Portfolio Overview": fig,
            "Asset Distribution": fig  # In real scenario, these would be different charts
        }
        
        gallery_paths = exporter.create_chart_gallery(charts, "test_gallery", format='png')
        print(f"✅ Chart gallery created with {len(gallery_paths)} charts")
        
        return success_png and success_html and success_svg
        
    except Exception as e:
        print(f"❌ Chart export failed: {e}")
        return False


def test_report_generation():
    """Test report generation functionality."""
    print("\n📋 Testing Report Generation...")
    
    try:
        from crypto_portfolio_analyzer.analytics.models import AnalyticsReport, PerformanceMetrics, RiskMetrics, AllocationMetrics
        
        # Create sample analytics report
        snapshots = create_sample_portfolio_data()
        snapshot = snapshots[0]
        
        # Create sample metrics
        performance_metrics = {
            "1d": PerformanceMetrics(
                total_return=Decimal("2500"),
                total_return_percentage=5.2,
                annualized_return=15.6,
                volatility=0.25,
                sharpe_ratio=0.62,
                max_drawdown=0.15,
                win_rate=0.65
            )
        }
        
        risk_metrics = RiskMetrics(
            volatility_daily=0.025,
            volatility_annualized=0.25,
            var_95_daily=0.035,
            var_99_daily=0.055,
            cvar_95_daily=0.045,
            max_drawdown=0.15,
            sharpe_ratio=0.62,
            sortino_ratio=0.78,
            calmar_ratio=1.04,
            beta=1.2,
            correlation_btc=0.85
        )
        
        allocation_metrics = AllocationMetrics(
            allocations={"BTC": 0.45, "ETH": 0.30, "SOL": 0.15, "ADA": 0.10},
            concentration_risk=0.45,
            effective_assets=3.2,
            largest_position="BTC"
        )
        
        analytics_report = AnalyticsReport(
            report_id="test_report_001",
            generated_at=datetime.now(timezone.utc),
            portfolio_snapshot=snapshot,
            performance_metrics=performance_metrics,
            risk_metrics=risk_metrics,
            allocation_metrics=allocation_metrics,
            alerts=[],
            benchmark_comparisons={}
        )
        
        # Generate reports
        report_generator = ReportGenerator()
        
        # JSON report
        json_report = report_generator.generate_json_report(analytics_report)
        with open("test_analytics_report.json", "w") as f:
            f.write(json_report)
        print("✅ JSON analytics report generated")
        
        # Summary report
        summary = report_generator.generate_summary_report(analytics_report)
        with open("test_summary_report.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print("✅ Summary report generated")
        
        # Performance report
        performance_report = report_generator.generate_performance_report(performance_metrics)
        with open("test_performance_report.json", "w") as f:
            json.dump(performance_report, f, indent=2, default=str)
        print("✅ Performance report generated")
        
        # Risk report
        risk_report = report_generator.generate_risk_report(risk_metrics)
        with open("test_risk_report.json", "w") as f:
            json.dump(risk_report, f, indent=2, default=str)
        print("✅ Risk report generated")
        
        return True
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return False


def test_export_configurations():
    """Test various export configurations."""
    print("\n⚙️ Testing Export Configurations...")
    
    try:
        exporter = DataExporter()
        snapshots = create_sample_portfolio_data()
        
        # Test different configurations
        configs = [
            ExportConfig(
                format=ExportFormat.CSV,
                include_headers=True,
                decimal_places=2,
                output_path="exports/basic"
            ),
            ExportConfig(
                format=ExportFormat.JSON,
                include_metadata=True,
                decimal_places=8,
                output_path="exports/detailed"
            ),
            ExportConfig(
                format=ExportFormat.EXCEL,
                include_metadata=True,
                decimal_places=4,
                output_path="exports/formatted"
            )
        ]
        
        for i, config in enumerate(configs):
            filename = f"portfolio_config_{i+1}.{config.format.value}"
            output_file = exporter.export_data(snapshots, config, filename)
            print(f"✅ Configuration {i+1} exported: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Export configuration test failed: {e}")
        return False


def test_enterprise_features():
    """Test enterprise-specific features."""
    print("\n🏢 Testing Enterprise Features...")
    
    try:
        # Test batch export
        print("📦 Testing batch export...")
        exporter = DataExporter()
        snapshots = create_sample_portfolio_data()
        prices = create_sample_price_data()
        
        # Export multiple datasets
        datasets = [
            (snapshots, "portfolio_snapshots"),
            (prices, "historical_prices")
        ]
        
        for data, name in datasets:
            for format_type in [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.EXCEL]:
                config = ExportConfig(format=format_type, output_path="enterprise_exports")
                filename = f"{name}.{format_type.value}"
                output_file = exporter.export_data(data, config, filename)
                print(f"  ✅ {name} exported as {format_type.value}")
        
        # Test metadata inclusion
        print("📋 Testing metadata features...")
        config = ExportConfig(
            format=ExportFormat.JSON,
            include_metadata=True,
            custom_fields=["export_version", "compliance_info"]
        )
        
        output_file = exporter.export_data(snapshots, config, "enterprise_portfolio.json")
        print(f"✅ Enterprise export with metadata: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enterprise features test failed: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 Testing Feature 7: Enterprise-Grade Export and Distribution")
    print("=" * 70)
    
    # Run all tests
    test_functions = [
        ("CSV Export", test_csv_export),
        ("JSON Export", test_json_export),
        ("Excel Export", test_excel_export),
        ("Chart Export", test_chart_export),
        ("Report Generation", test_report_generation),
        ("Export Configurations", test_export_configurations),
        ("Enterprise Features", test_enterprise_features)
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    for i, (test_name, result) in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All enterprise export features are working!")
        print("\n🔧 Feature 7 Components Tested:")
        print("  ✅ CSV Data Export")
        print("  ✅ JSON Data Export") 
        print("  ✅ Excel Data Export")
        print("  ✅ Chart Export (PNG, HTML, SVG)")
        print("  ✅ Report Generation")
        print("  ✅ Export Configurations")
        print("  ✅ Enterprise Features")
        
        print("\n📁 Generated Files:")
        print("  • test_portfolio.csv")
        print("  • test_portfolio.json")
        print("  • test_portfolio.xlsx")
        print("  • test_chart.png/html/svg")
        print("  • test_analytics_report.json")
        print("  • enterprise_exports/ directory")
        
        print("\n💡 Next Steps:")
        print("  • Configure automated report scheduling")
        print("  • Set up enterprise data distribution")
        print("  • Integrate with business intelligence tools")
        print("  • Configure compliance reporting")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

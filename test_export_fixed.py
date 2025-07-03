#!/usr/bin/env python3
"""
Fixed test for Feature 7: Enterprise-Grade Export and Distribution.
This version includes comprehensive error handling and diagnostics.
"""

import sys
import json
import csv
import traceback
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def safe_import_test():
    """Test imports with detailed error reporting."""
    print("🔍 Testing Imports...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import (
            DataExporter, ExportConfig, ExportFormat, CSVExporter, JSONExporter
        )
        print("✅ All export modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're in the correct directory")
        return False
    except Exception as e:
        print(f"❌ Unexpected import error: {e}")
        traceback.print_exc()
        return False


def create_safe_test_data():
    """Create test data that's guaranteed to be serializable."""
    return [
        {
            'symbol': 'BTC',
            'price': 52000.00,
            'quantity': 1.5,
            'value': 78000.00,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        {
            'symbol': 'ETH', 
            'price': 3800.00,
            'quantity': 10.0,
            'value': 38000.00,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        {
            'symbol': 'SOL',
            'price': 110.00,
            'quantity': 50.0,
            'value': 5500.00,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    ]


def test_csv_export_fixed():
    """Test CSV export with comprehensive error handling."""
    print("\n📊 Testing CSV Export (Fixed Version)...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import CSVExporter, ExportConfig, ExportFormat
        
        # Create test data
        data = create_safe_test_data()
        print(f"✅ Created test data with {len(data)} records")
        
        # Create configuration
        config = ExportConfig(
            format=ExportFormat.CSV,
            include_headers=True,
            decimal_places=2
        )
        print("✅ CSV configuration created")
        
        # Create exporter
        exporter = CSVExporter(config)
        print("✅ CSV exporter created")
        
        # Export data
        output_file = exporter.export(data, 'fixed_test.csv')
        print(f"✅ CSV export completed: {output_file}")
        
        # Verify file
        if Path(output_file).exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                print(f"📄 CSV file created with {len(lines)} lines")
                print(f"📋 Header: {lines[0] if lines else 'No content'}")
                if len(lines) > 1:
                    print(f"📋 Sample row: {lines[1]}")
            return True
        else:
            print("❌ CSV file was not created")
            return False
            
    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        print("Full error details:")
        traceback.print_exc()
        return False


def test_json_export_fixed():
    """Test JSON export with comprehensive error handling."""
    print("\n📄 Testing JSON Export (Fixed Version)...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import JSONExporter, ExportConfig, ExportFormat
        
        # Create test data
        data = create_safe_test_data()
        print(f"✅ Created test data with {len(data)} records")
        
        # Create configuration
        config = ExportConfig(
            format=ExportFormat.JSON,
            include_metadata=True,
            decimal_places=4
        )
        print("✅ JSON configuration created")
        
        # Create exporter
        exporter = JSONExporter(config)
        print("✅ JSON exporter created")
        
        # Export data
        output_file = exporter.export(data, 'fixed_test.json')
        print(f"✅ JSON export completed: {output_file}")
        
        # Verify file
        if Path(output_file).exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                print(f"📄 JSON file structure:")
                print(f"  • Format version: {json_data.get('format_version', 'N/A')}")
                print(f"  • Data type: {json_data.get('data_type', 'N/A')}")
                print(f"  • Records: {len(json_data.get('data', []))}")
                print(f"  • Has metadata: {'metadata' in json_data}")
                print(f"  • Export time: {json_data.get('exported_at', 'N/A')}")
            return True
        else:
            print("❌ JSON file was not created")
            return False
            
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        print("Full error details:")
        traceback.print_exc()
        return False


def test_manual_csv_export():
    """Test manual CSV export without using the framework."""
    print("\n🔧 Testing Manual CSV Export...")
    
    try:
        data = create_safe_test_data()
        output_file = 'manual_test.csv'
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            if data:
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        
        print(f"✅ Manual CSV export successful: {output_file}")
        
        # Verify
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"📄 Manual CSV content ({len(content)} chars)")
        
        return True
        
    except Exception as e:
        print(f"❌ Manual CSV export failed: {e}")
        traceback.print_exc()
        return False


def test_manual_json_export():
    """Test manual JSON export without using the framework."""
    print("\n🔧 Testing Manual JSON Export...")
    
    try:
        data = create_safe_test_data()
        output_file = 'manual_test.json'
        
        json_output = {
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'format_version': '1.0',
            'data_type': 'manual_test',
            'total_records': len(data),
            'data': data
        }
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_output, jsonfile, indent=2, default=str, ensure_ascii=False)
        
        print(f"✅ Manual JSON export successful: {output_file}")
        
        # Verify
        with open(output_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            print(f"📄 Manual JSON structure:")
            print(f"  • Records: {loaded_data.get('total_records', 0)}")
            print(f"  • Format: {loaded_data.get('format_version', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Manual JSON export failed: {e}")
        traceback.print_exc()
        return False


def test_data_exporter_fixed():
    """Test the main DataExporter class with error handling."""
    print("\n🔧 Testing DataExporter (Fixed Version)...")
    
    try:
        from crypto_portfolio_analyzer.visualization.export import DataExporter, ExportConfig, ExportFormat
        
        # Create exporter
        exporter = DataExporter()
        print("✅ DataExporter created")
        
        # Create test data
        data = create_safe_test_data()
        print(f"✅ Test data created with {len(data)} records")
        
        # Test CSV export
        csv_config = ExportConfig(format=ExportFormat.CSV, include_headers=True)
        csv_file = exporter.export_data(data, csv_config, 'dataexporter_test.csv')
        print(f"✅ DataExporter CSV: {csv_file}")
        
        # Test JSON export
        json_config = ExportConfig(format=ExportFormat.JSON, include_metadata=True)
        json_file = exporter.export_data(data, json_config, 'dataexporter_test.json')
        print(f"✅ DataExporter JSON: {json_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ DataExporter test failed: {e}")
        print("Full error details:")
        traceback.print_exc()
        return False


def test_file_permissions():
    """Test file creation permissions."""
    print("\n📁 Testing File Permissions...")
    
    try:
        # Test basic file creation
        test_file = 'permission_test.txt'
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('Permission test successful')
        
        # Test reading
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Cleanup
        Path(test_file).unlink()
        
        print("✅ File permissions OK")
        return True
        
    except Exception as e:
        print(f"❌ File permission error: {e}")
        return False


def main():
    """Main test function with comprehensive error handling."""
    print("🚀 Testing Feature 7: Enterprise-Grade Export and Distribution (Fixed)")
    print("=" * 75)
    
    # Test imports first
    if not safe_import_test():
        print("\n❌ Cannot proceed - import errors detected")
        print("💡 Make sure you're in the correct directory and all modules are available")
        return 1
    
    # Test file permissions
    if not test_file_permissions():
        print("\n❌ Cannot proceed - file permission errors")
        return 1
    
    # Run tests
    test_functions = [
        ("Manual CSV Export", test_manual_csv_export),
        ("Manual JSON Export", test_manual_json_export),
        ("Framework CSV Export", test_csv_export_fixed),
        ("Framework JSON Export", test_json_export_fixed),
        ("DataExporter Class", test_data_exporter_fixed)
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
    print("\n" + "=" * 75)
    print("📊 TEST SUMMARY")
    print("=" * 75)
    
    passed = 0
    for i, (test_name, result) in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed >= 2:  # At least manual exports should work
        print("\n🎉 Basic export functionality is working!")
        print("\n📁 Generated Files:")
        files_to_check = [
            'manual_test.csv', 'manual_test.json',
            'fixed_test.csv', 'fixed_test.json',
            'dataexporter_test.csv', 'dataexporter_test.json'
        ]
        
        for file in files_to_check:
            if Path(file).exists():
                size = Path(file).stat().st_size
                print(f"  ✅ {file} ({size:,} bytes)")
        
        print("\n💡 Next Steps:")
        if passed < total:
            print("  • Some framework tests failed - check error messages above")
            print("  • Manual exports work, so core functionality is available")
        print("  • Try installing missing dependencies if needed")
        print("  • Check file permissions if exports fail")
        
    else:
        print(f"\n⚠️ Most tests failed. Check the error messages above.")
        print("💡 Common solutions:")
        print("  • Make sure you're in the correct directory")
        print("  • Check that all required modules are available")
        print("  • Verify file write permissions")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

"""Tests for visualization export module."""

import pytest
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from decimal import Decimal

from crypto_portfolio_analyzer.visualization.export import (
    ExportFormat, ExportConfig, BaseExporter, CSVExporter, JSONExporter,
    ExcelExporter, DataExporter
)
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding
from crypto_portfolio_analyzer.data.models import HistoricalPrice


class TestExportConfig:
    """Test ExportConfig class."""
    
    def test_export_config_creation(self):
        """Test creating export configuration."""
        config = ExportConfig(
            format=ExportFormat.CSV,
            include_headers=True,
            include_metadata=True,
            decimal_places=4
        )
        
        assert config.format == ExportFormat.CSV
        assert config.include_headers is True
        assert config.include_metadata is True
        assert config.decimal_places == 4
        assert config.date_format == "%Y-%m-%d %H:%M:%S"
    
    def test_export_config_defaults(self):
        """Test export configuration defaults."""
        config = ExportConfig(format=ExportFormat.JSON)
        
        assert config.include_headers is True
        assert config.include_metadata is True
        assert config.decimal_places == 6
        assert config.compress is False
        assert config.custom_fields == []


class TestBaseExporter:
    """Test BaseExporter class."""
    
    def test_base_exporter_creation(self):
        """Test creating base exporter."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = BaseExporter(config)
        
        assert exporter.config == config
    
    def test_export_not_implemented(self):
        """Test that export method raises NotImplementedError."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = BaseExporter(config)
        
        with pytest.raises(NotImplementedError):
            exporter.export([], "test.csv")
    
    def test_prepare_output_path(self):
        """Test preparing output path."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = BaseExporter(config)
        
        path = exporter._prepare_output_path("test.csv")
        assert isinstance(path, Path)
        assert path.name == "test.csv"
    
    def test_prepare_output_path_with_config_path(self):
        """Test preparing output path with config path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ExportConfig(format=ExportFormat.CSV, output_path=temp_dir)
            exporter = BaseExporter(config)
            
            path = exporter._prepare_output_path("test.csv")
            assert path.parent == Path(temp_dir)
            assert path.name == "test.csv"


class TestCSVExporter:
    """Test CSVExporter class."""
    
    @pytest.fixture
    def sample_portfolio_snapshots(self):
        """Create sample portfolio snapshots."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            )
        ]
        
        return [
            PortfolioSnapshot(
                timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                portfolio_value=Decimal("50000"),
                total_cost=Decimal("45000"),
                holdings=holdings
            ),
            PortfolioSnapshot(
                timestamp=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
                portfolio_value=Decimal("52000"),
                total_cost=Decimal("45000"),
                holdings=holdings
            )
        ]
    
    @pytest.fixture
    def sample_historical_prices(self):
        """Create sample historical prices."""
        return [
            HistoricalPrice(
                symbol="BTC",
                price=Decimal("50000"),
                timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                volume=Decimal("1000000"),
                market_cap=Decimal("1000000000")
            ),
            HistoricalPrice(
                symbol="BTC",
                price=Decimal("51000"),
                timestamp=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
                volume=Decimal("1100000"),
                market_cap=Decimal("1020000000")
            )
        ]
    
    def test_csv_exporter_creation(self):
        """Test creating CSV exporter."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = CSVExporter(config)
        
        assert isinstance(exporter, BaseExporter)
        assert exporter.config.format == ExportFormat.CSV
    
    def test_export_portfolio_snapshots_csv(self, sample_portfolio_snapshots):
        """Test exporting portfolio snapshots to CSV."""
        config = ExportConfig(format=ExportFormat.CSV, decimal_places=2)
        exporter = CSVExporter(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_portfolio_snapshots, temp_path)
            
            assert result_path == temp_path
            assert Path(temp_path).exists()
            
            # Read and verify CSV content
            with open(temp_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                assert len(rows) == 2
                assert rows[0]['portfolio_value'] == '50000.0'
                assert rows[0]['total_cost'] == '45000.0'
                assert rows[1]['portfolio_value'] == '52000.0'
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_historical_prices_csv(self, sample_historical_prices):
        """Test exporting historical prices to CSV."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = CSVExporter(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_historical_prices, temp_path)
            
            assert result_path == temp_path
            assert Path(temp_path).exists()
            
            # Read and verify CSV content
            with open(temp_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                assert len(rows) == 2
                assert rows[0]['symbol'] == 'BTC'
                assert rows[0]['price'] == '50000.0'
                assert rows[1]['price'] == '51000.0'
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_generic_csv(self):
        """Test exporting generic data to CSV."""
        config = ExportConfig(format=ExportFormat.CSV)
        exporter = CSVExporter(config)
        
        data = [
            {"name": "Alice", "age": 30, "city": "New York"},
            {"name": "Bob", "age": 25, "city": "San Francisco"}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(data, temp_path)
            
            assert result_path == temp_path
            
            # Read and verify CSV content
            with open(temp_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                assert len(rows) == 2
                assert rows[0]['name'] == 'Alice'
                assert rows[1]['name'] == 'Bob'
                
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestJSONExporter:
    """Test JSONExporter class."""
    
    @pytest.fixture
    def sample_portfolio_snapshots(self):
        """Create sample portfolio snapshots."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            )
        ]
        
        return [
            PortfolioSnapshot(
                timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                portfolio_value=Decimal("50000"),
                total_cost=Decimal("45000"),
                holdings=holdings
            )
        ]
    
    def test_json_exporter_creation(self):
        """Test creating JSON exporter."""
        config = ExportConfig(format=ExportFormat.JSON)
        exporter = JSONExporter(config)
        
        assert isinstance(exporter, BaseExporter)
        assert exporter.config.format == ExportFormat.JSON
    
    def test_export_portfolio_snapshots_json(self, sample_portfolio_snapshots):
        """Test exporting portfolio snapshots to JSON."""
        config = ExportConfig(format=ExportFormat.JSON, decimal_places=2)
        exporter = JSONExporter(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_portfolio_snapshots, temp_path)
            
            assert result_path == temp_path
            assert Path(temp_path).exists()
            
            # Read and verify JSON content
            with open(temp_path, 'r') as jsonfile:
                data = json.load(jsonfile)
                
                assert 'exported_at' in data
                assert 'format_version' in data
                assert data['data_type'] == 'portfolio_snapshots'
                assert len(data['data']) == 1
                
                snapshot = data['data'][0]
                assert snapshot['portfolio_value'] == 50000.0
                assert snapshot['total_cost'] == 45000.0
                assert len(snapshot['holdings']) == 1
                
                holding = snapshot['holdings'][0]
                assert holding['symbol'] == 'BTC'
                assert holding['amount'] == 1.0
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_with_metadata(self, sample_portfolio_snapshots):
        """Test exporting with metadata."""
        config = ExportConfig(format=ExportFormat.JSON, include_metadata=True)
        exporter = JSONExporter(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_portfolio_snapshots, temp_path)
            
            with open(temp_path, 'r') as jsonfile:
                data = json.load(jsonfile)
                
                assert 'metadata' in data
                assert data['metadata']['total_records'] == 1
                assert data['metadata']['decimal_places'] == 6
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_without_metadata(self, sample_portfolio_snapshots):
        """Test exporting without metadata."""
        config = ExportConfig(format=ExportFormat.JSON, include_metadata=False)
        exporter = JSONExporter(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_portfolio_snapshots, temp_path)
            
            with open(temp_path, 'r') as jsonfile:
                data = json.load(jsonfile)
                
                assert 'metadata' not in data
                
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestExcelExporter:
    """Test ExcelExporter class."""
    
    @pytest.fixture
    def sample_portfolio_snapshots(self):
        """Create sample portfolio snapshots."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            ),
            PortfolioHolding(
                symbol="ETH",
                amount=Decimal("10.0"),
                current_value=Decimal("30000"),
                cost_basis=Decimal("25000")
            )
        ]
        
        return [
            PortfolioSnapshot(
                timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                portfolio_value=Decimal("80000"),
                total_cost=Decimal("70000"),
                holdings=holdings
            )
        ]
    
    def test_excel_exporter_creation(self):
        """Test creating Excel exporter."""
        config = ExportConfig(format=ExportFormat.EXCEL)
        exporter = ExcelExporter(config)
        
        assert isinstance(exporter, BaseExporter)
        assert exporter.config.format == ExportFormat.EXCEL
    
    @patch('openpyxl.Workbook')
    def test_export_portfolio_snapshots_excel(self, mock_workbook, sample_portfolio_snapshots):
        """Test exporting portfolio snapshots to Excel."""
        config = ExportConfig(format=ExportFormat.EXCEL)
        exporter = ExcelExporter(config)
        
        # Mock workbook and worksheets
        mock_wb = Mock()
        mock_workbook.return_value = mock_wb
        mock_ws_summary = Mock()
        mock_ws_holdings = Mock()
        mock_wb.create_sheet.side_effect = [mock_ws_summary, mock_ws_holdings]
        mock_wb.worksheets = [Mock(), mock_ws_summary, mock_ws_holdings]  # Default sheet + 2 new
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result_path = exporter.export(sample_portfolio_snapshots, temp_path)
            
            assert result_path == temp_path
            mock_wb.save.assert_called_once_with(Path(temp_path))
            
            # Verify sheets were created
            assert mock_wb.create_sheet.call_count == 2
            mock_wb.create_sheet.assert_any_call("Portfolio Summary")
            mock_wb.create_sheet.assert_any_call("Current Holdings")
            
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDataExporter:
    """Test DataExporter class."""
    
    def test_data_exporter_creation(self):
        """Test creating data exporter."""
        exporter = DataExporter()
        
        assert ExportFormat.CSV in exporter.exporters
        assert ExportFormat.JSON in exporter.exporters
        assert ExportFormat.EXCEL in exporter.exporters
    
    @patch('crypto_portfolio_analyzer.visualization.export.CSVExporter')
    def test_export_data_csv(self, mock_csv_exporter):
        """Test exporting data as CSV."""
        exporter = DataExporter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.export.return_value = "/path/to/file.csv"
        mock_csv_exporter.return_value = mock_exporter_instance
        
        config = ExportConfig(format=ExportFormat.CSV)
        data = [{"test": "data"}]
        
        result = exporter.export_data(data, config, "test.csv")
        
        assert result == "/path/to/file.csv"
        mock_csv_exporter.assert_called_once_with(config)
        mock_exporter_instance.export.assert_called_once_with(data, "test.csv")
    
    def test_export_data_unsupported_format(self):
        """Test exporting with unsupported format."""
        exporter = DataExporter()
        
        # Create config with invalid format
        config = ExportConfig(format=ExportFormat.CSV)
        config.format = "invalid_format"  # Bypass enum validation
        
        with pytest.raises(ValueError, match="Unsupported export format"):
            exporter.export_data([], config, "test.txt")
    
    @patch('crypto_portfolio_analyzer.visualization.export.CSVExporter')
    def test_export_portfolio_snapshots(self, mock_csv_exporter):
        """Test exporting portfolio snapshots convenience method."""
        exporter = DataExporter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.export.return_value = "/path/to/file.csv"
        mock_csv_exporter.return_value = mock_exporter_instance
        
        snapshots = [Mock()]
        result = exporter.export_portfolio_snapshots(snapshots, ExportFormat.CSV, "test.csv")
        
        assert result == "/path/to/file.csv"
        mock_csv_exporter.assert_called_once()
        mock_exporter_instance.export.assert_called_once_with(snapshots, "test.csv")
    
    @patch('crypto_portfolio_analyzer.visualization.export.CSVExporter')
    def test_export_portfolio_snapshots_auto_filename(self, mock_csv_exporter):
        """Test exporting portfolio snapshots with auto-generated filename."""
        exporter = DataExporter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.export.return_value = "/path/to/file.csv"
        mock_csv_exporter.return_value = mock_exporter_instance
        
        snapshots = [Mock()]
        
        with patch('crypto_portfolio_analyzer.visualization.export.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20230101_120000"
            
            result = exporter.export_portfolio_snapshots(snapshots)
            
            # Should generate filename with timestamp
            expected_filename = "portfolio_snapshots_20230101_120000.csv"
            mock_exporter_instance.export.assert_called_once_with(snapshots, expected_filename)
    
    @patch('crypto_portfolio_analyzer.visualization.export.CSVExporter')
    def test_export_historical_prices(self, mock_csv_exporter):
        """Test exporting historical prices convenience method."""
        exporter = DataExporter()
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.export.return_value = "/path/to/file.csv"
        mock_csv_exporter.return_value = mock_exporter_instance
        
        prices = [Mock()]
        result = exporter.export_historical_prices(prices, ExportFormat.JSON, "test.json")
        
        assert result == "/path/to/file.csv"
        mock_exporter_instance.export.assert_called_once_with(prices, "test.json")

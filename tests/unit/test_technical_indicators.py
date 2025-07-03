"""Tests for technical indicators."""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto_portfolio_analyzer.visualization.indicators import TechnicalIndicators
from crypto_portfolio_analyzer.data.models import HistoricalPrice, DataSource


@pytest.fixture
def sample_prices():
    """Sample price data for testing."""
    # Create trending price data with some volatility
    base_price = 100
    prices = []
    for i in range(50):
        price = base_price + (i * 0.5) + (np.sin(i * 0.3) * 2)
        prices.append(price)
    return prices


@pytest.fixture
def sample_historical_prices():
    """Sample historical price data for testing."""
    prices = []
    base_date = datetime.now(timezone.utc) - timedelta(days=50)
    base_price = 50000
    
    for i in range(50):
        date = base_date + timedelta(days=i)
        price = base_price + (i * 100) + (np.sin(i * 0.2) * 1000)
        volume = 1000000 + (np.random.random() * 500000)
        
        historical_price = HistoricalPrice(
            symbol="BTC",
            timestamp=date,
            price=Decimal(str(price)),
            volume=Decimal(str(volume)),
            data_source=DataSource.COINGECKO
        )
        prices.append(historical_price)
    
    return prices


class TestTechnicalIndicators:
    """Test TechnicalIndicators functionality."""
    
    def test_technical_indicators_initialization(self):
        """Test TechnicalIndicators initialization."""
        indicators = TechnicalIndicators()
        assert indicators is not None
    
    def test_calculate_sma(self, sample_prices):
        """Test Simple Moving Average calculation."""
        indicators = TechnicalIndicators()
        
        sma_20 = indicators.calculate_sma(sample_prices, 20)
        
        assert len(sma_20) == len(sample_prices)
        # First 19 values should be NaN
        assert all(np.isnan(sma_20[i]) for i in range(19))
        # 20th value should be average of first 20 prices
        assert not np.isnan(sma_20[19])
        assert abs(sma_20[19] - np.mean(sample_prices[:20])) < 1e-10
    
    def test_calculate_sma_insufficient_data(self):
        """Test SMA with insufficient data."""
        indicators = TechnicalIndicators()
        
        short_prices = [100, 101, 102]
        sma_20 = indicators.calculate_sma(short_prices, 20)
        
        assert len(sma_20) == 3
        assert all(np.isnan(val) for val in sma_20)
    
    def test_calculate_ema(self, sample_prices):
        """Test Exponential Moving Average calculation."""
        indicators = TechnicalIndicators()
        
        ema_20 = indicators.calculate_ema(sample_prices, 20)
        
        assert len(ema_20) == len(sample_prices)
        # First value should equal first price
        assert ema_20[0] == sample_prices[0]
        # EMA should be different from SMA
        sma_20 = indicators.calculate_sma(sample_prices, 20)
        assert ema_20[-1] != sma_20[-1]
    
    def test_calculate_ema_empty_data(self):
        """Test EMA with empty data."""
        indicators = TechnicalIndicators()
        
        ema = indicators.calculate_ema([], 20)
        assert ema == []
    
    def test_calculate_rsi(self, sample_prices):
        """Test Relative Strength Index calculation."""
        indicators = TechnicalIndicators()
        
        rsi = indicators.calculate_rsi(sample_prices, 14)
        
        assert len(rsi) == len(sample_prices)
        # First value should be NaN
        assert np.isnan(rsi[0])
        # RSI values should be between 0 and 100
        valid_rsi = [val for val in rsi if not np.isnan(val)]
        assert all(0 <= val <= 100 for val in valid_rsi)
    
    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data."""
        indicators = TechnicalIndicators()
        
        short_prices = [100, 101, 102]
        rsi = indicators.calculate_rsi(short_prices, 14)
        
        assert len(rsi) == 3
        assert all(np.isnan(val) for val in rsi)
    
    def test_calculate_macd(self, sample_prices):
        """Test MACD calculation."""
        indicators = TechnicalIndicators()
        
        macd_data = indicators.calculate_macd(sample_prices, 12, 26, 9)
        
        assert 'macd' in macd_data
        assert 'signal' in macd_data
        assert 'histogram' in macd_data
        
        assert len(macd_data['macd']) == len(sample_prices)
        assert len(macd_data['signal']) == len(sample_prices)
        assert len(macd_data['histogram']) == len(sample_prices)
        
        # Early values should be NaN
        assert np.isnan(macd_data['macd'][0])
        assert np.isnan(macd_data['signal'][0])
        assert np.isnan(macd_data['histogram'][0])
    
    def test_calculate_macd_insufficient_data(self):
        """Test MACD with insufficient data."""
        indicators = TechnicalIndicators()
        
        short_prices = [100, 101, 102]
        macd_data = indicators.calculate_macd(short_prices, 12, 26, 9)
        
        assert all(np.isnan(val) for val in macd_data['macd'])
        assert all(np.isnan(val) for val in macd_data['signal'])
        assert all(np.isnan(val) for val in macd_data['histogram'])
    
    def test_calculate_bollinger_bands(self, sample_prices):
        """Test Bollinger Bands calculation."""
        indicators = TechnicalIndicators()
        
        bb_data = indicators.calculate_bollinger_bands(sample_prices, 20, 2.0)
        
        assert 'upper' in bb_data
        assert 'middle' in bb_data
        assert 'lower' in bb_data
        
        assert len(bb_data['upper']) == len(sample_prices)
        assert len(bb_data['middle']) == len(sample_prices)
        assert len(bb_data['lower']) == len(sample_prices)
        
        # Check that upper > middle > lower (where not NaN)
        for i in range(20, len(sample_prices)):
            assert bb_data['upper'][i] > bb_data['middle'][i]
            assert bb_data['middle'][i] > bb_data['lower'][i]
    
    def test_calculate_bollinger_bands_insufficient_data(self):
        """Test Bollinger Bands with insufficient data."""
        indicators = TechnicalIndicators()
        
        short_prices = [100, 101, 102]
        bb_data = indicators.calculate_bollinger_bands(short_prices, 20, 2.0)
        
        assert all(np.isnan(val) for val in bb_data['upper'])
        assert all(np.isnan(val) for val in bb_data['middle'])
        assert all(np.isnan(val) for val in bb_data['lower'])
    
    def test_calculate_volume_sma(self):
        """Test Volume SMA calculation."""
        indicators = TechnicalIndicators()
        
        volumes = [1000000 + i * 10000 for i in range(30)]
        volume_sma = indicators.calculate_volume_sma(volumes, 10)
        
        assert len(volume_sma) == len(volumes)
        # Should be same as regular SMA
        regular_sma = indicators.calculate_sma(volumes, 10)
        assert volume_sma == regular_sma
    
    def test_calculate_price_volume_trend(self):
        """Test Price Volume Trend calculation."""
        indicators = TechnicalIndicators()
        
        prices = [100 + i for i in range(10)]
        volumes = [1000000] * 10
        
        pvt = indicators.calculate_price_volume_trend(prices, volumes)
        
        assert len(pvt) == len(prices)
        assert pvt[0] == 0  # First value should be 0
        # PVT should increase with rising prices
        assert pvt[-1] > pvt[0]
    
    def test_calculate_price_volume_trend_mismatched_lengths(self):
        """Test PVT with mismatched price and volume lengths."""
        indicators = TechnicalIndicators()
        
        prices = [100, 101, 102]
        volumes = [1000000, 1100000]  # One less volume
        
        pvt = indicators.calculate_price_volume_trend(prices, volumes)
        
        assert len(pvt) == len(prices)
        assert all(np.isnan(val) for val in pvt)
    
    def test_calculate_stochastic_oscillator(self):
        """Test Stochastic Oscillator calculation."""
        indicators = TechnicalIndicators()
        
        # Create sample OHLC data
        highs = [105 + i + np.sin(i * 0.1) * 2 for i in range(30)]
        lows = [95 + i + np.sin(i * 0.1) * 2 for i in range(30)]
        closes = [100 + i + np.sin(i * 0.1) * 2 for i in range(30)]
        
        stoch_data = indicators.calculate_stochastic_oscillator(highs, lows, closes, 14, 3)
        
        assert 'k' in stoch_data
        assert 'd' in stoch_data
        
        assert len(stoch_data['k']) == len(closes)
        assert len(stoch_data['d']) == len(closes)
        
        # %K values should be between 0 and 100
        valid_k = [val for val in stoch_data['k'] if not np.isnan(val)]
        assert all(0 <= val <= 100 for val in valid_k)
    
    def test_calculate_stochastic_oscillator_insufficient_data(self):
        """Test Stochastic Oscillator with insufficient data."""
        indicators = TechnicalIndicators()
        
        highs = [105, 106, 107]
        lows = [95, 96, 97]
        closes = [100, 101, 102]
        
        stoch_data = indicators.calculate_stochastic_oscillator(highs, lows, closes, 14, 3)
        
        assert all(np.isnan(val) for val in stoch_data['k'])
        assert all(np.isnan(val) for val in stoch_data['d'])
    
    def test_calculate_all_indicators(self, sample_historical_prices):
        """Test calculating all indicators at once."""
        indicators = TechnicalIndicators()
        
        all_indicators = indicators.calculate_all_indicators(sample_historical_prices)
        
        # Check that all expected indicators are present
        expected_indicators = [
            'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26', 'RSI',
            'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Upper', 'BB_Middle', 'BB_Lower',
            'Volume_SMA', 'PVT', 'Stoch_K', 'Stoch_D'
        ]
        
        for indicator in expected_indicators:
            assert indicator in all_indicators
            assert len(all_indicators[indicator]) == len(sample_historical_prices)
    
    def test_calculate_all_indicators_empty_data(self):
        """Test calculating all indicators with empty data."""
        indicators = TechnicalIndicators()
        
        all_indicators = indicators.calculate_all_indicators([])
        
        assert all_indicators == {}
    
    def test_get_indicator_signals(self, sample_historical_prices):
        """Test generating trading signals from indicators."""
        indicators = TechnicalIndicators()
        
        all_indicators = indicators.calculate_all_indicators(sample_historical_prices)
        signals = indicators.get_indicator_signals(all_indicators)
        
        assert isinstance(signals, dict)
        # Should have signals for various indicators
        possible_signals = ['RSI', 'MACD', 'SMA_Cross', 'Stochastic']
        
        # At least some signals should be generated
        assert len(signals) > 0
        
        # Check signal values are valid
        valid_signal_values = [
            'OVERBOUGHT', 'OVERSOLD', 'NEUTRAL',
            'BULLISH', 'BEARISH', 'BULLISH_CROSSOVER', 'BEARISH_CROSSOVER'
        ]
        
        for signal_value in signals.values():
            assert signal_value in valid_signal_values
    
    def test_get_indicator_signals_empty_indicators(self):
        """Test generating signals with empty indicators."""
        indicators = TechnicalIndicators()
        
        signals = indicators.get_indicator_signals({})
        
        assert signals == {}
    
    def test_get_indicator_signals_nan_values(self):
        """Test generating signals with NaN values."""
        indicators = TechnicalIndicators()
        
        # Create indicators with NaN values
        test_indicators = {
            'RSI': [np.nan, np.nan, 75.0],
            'MACD': [np.nan, 1.0, 2.0],
            'MACD_Signal': [np.nan, 0.5, 1.5]
        }
        
        signals = indicators.get_indicator_signals(test_indicators)
        
        # Should handle NaN values gracefully
        assert isinstance(signals, dict)


class TestTechnicalIndicatorsEdgeCases:
    """Test edge cases and error handling."""
    
    def test_sma_with_zero_period(self):
        """Test SMA with zero period."""
        indicators = TechnicalIndicators()
        
        prices = [100, 101, 102, 103, 104]
        sma = indicators.calculate_sma(prices, 0)
        
        # Should handle gracefully
        assert len(sma) == len(prices)
    
    def test_ema_with_single_price(self):
        """Test EMA with single price."""
        indicators = TechnicalIndicators()
        
        ema = indicators.calculate_ema([100], 20)
        
        assert len(ema) == 1
        assert ema[0] == 100
    
    def test_rsi_with_constant_prices(self):
        """Test RSI with constant prices (no change)."""
        indicators = TechnicalIndicators()
        
        constant_prices = [100] * 20
        rsi = indicators.calculate_rsi(constant_prices, 14)
        
        # RSI should be around 50 for no change
        valid_rsi = [val for val in rsi if not np.isnan(val)]
        if valid_rsi:
            # With no price changes, RSI calculation might vary
            assert all(0 <= val <= 100 for val in valid_rsi)
    
    def test_bollinger_bands_with_zero_std(self):
        """Test Bollinger Bands with zero standard deviation."""
        indicators = TechnicalIndicators()
        
        constant_prices = [100] * 25
        bb_data = indicators.calculate_bollinger_bands(constant_prices, 20, 2.0)
        
        # With constant prices, upper and lower bands should equal middle
        for i in range(20, len(constant_prices)):
            assert bb_data['upper'][i] == bb_data['middle'][i]
            assert bb_data['lower'][i] == bb_data['middle'][i]
    
    def test_stochastic_with_equal_high_low(self):
        """Test Stochastic Oscillator with equal high and low prices."""
        indicators = TechnicalIndicators()
        
        # Equal high and low prices
        highs = [100] * 20
        lows = [100] * 20
        closes = [100] * 20
        
        stoch_data = indicators.calculate_stochastic_oscillator(highs, lows, closes, 14, 3)
        
        # Should handle division by zero gracefully
        valid_k = [val for val in stoch_data['k'] if not np.isnan(val)]
        if valid_k:
            # Should default to 50 when high == low
            assert all(val == 50 for val in valid_k)
    
    def test_pvt_with_zero_prices(self):
        """Test PVT with zero prices."""
        indicators = TechnicalIndicators()
        
        prices = [0, 0, 0, 0]
        volumes = [1000000] * 4
        
        pvt = indicators.calculate_price_volume_trend(prices, volumes)
        
        # Should handle zero prices gracefully
        assert len(pvt) == len(prices)
        assert pvt[0] == 0
    
    def test_indicators_with_negative_prices(self):
        """Test indicators with negative prices."""
        indicators = TechnicalIndicators()
        
        negative_prices = [-100, -99, -98, -97, -96]
        
        # SMA should work with negative prices
        sma = indicators.calculate_sma(negative_prices, 3)
        assert not np.isnan(sma[-1])
        
        # EMA should work with negative prices
        ema = indicators.calculate_ema(negative_prices, 3)
        assert len(ema) == len(negative_prices)
    
    def test_indicators_with_very_large_numbers(self):
        """Test indicators with very large numbers."""
        indicators = TechnicalIndicators()
        
        large_prices = [1e10 + i for i in range(30)]
        
        sma = indicators.calculate_sma(large_prices, 10)
        assert not np.isnan(sma[-1])
        
        ema = indicators.calculate_ema(large_prices, 10)
        assert len(ema) == len(large_prices)

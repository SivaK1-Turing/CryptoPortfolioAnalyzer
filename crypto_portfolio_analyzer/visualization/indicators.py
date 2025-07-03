"""Technical indicators for cryptocurrency analysis."""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging

from ..data.models import HistoricalPrice

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Technical analysis indicators calculator."""
    
    def __init__(self):
        """Initialize technical indicators calculator."""
        pass
    
    def calculate_sma(self, prices: List[float], period: int = 20) -> List[float]:
        """Calculate Simple Moving Average.
        
        Args:
            prices: List of price values
            period: Moving average period
            
        Returns:
            List of SMA values
        """
        if len(prices) < period:
            return [np.nan] * len(prices)
        
        sma_values = []
        for i in range(len(prices)):
            if i < period - 1:
                sma_values.append(np.nan)
            else:
                sma = np.mean(prices[i - period + 1:i + 1])
                sma_values.append(sma)
        
        return sma_values
    
    def calculate_ema(self, prices: List[float], period: int = 20) -> List[float]:
        """Calculate Exponential Moving Average.
        
        Args:
            prices: List of price values
            period: EMA period
            
        Returns:
            List of EMA values
        """
        if not prices:
            return []
        
        ema_values = []
        multiplier = 2 / (period + 1)
        
        # First EMA value is the first price
        ema_values.append(prices[0])
        
        for i in range(1, len(prices)):
            ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)
        
        return ema_values
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index.
        
        Args:
            prices: List of price values
            period: RSI period
            
        Returns:
            List of RSI values
        """
        if len(prices) < period + 1:
            return [np.nan] * len(prices)
        
        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        rsi_values = [np.nan]  # First value is NaN
        
        # Calculate initial average gain and loss
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(deltas)):
            # Smoothed averages
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
        
        # Fill remaining values
        while len(rsi_values) < len(prices):
            rsi_values.append(np.nan)
        
        return rsi_values
    
    def calculate_macd(self, prices: List[float], 
                      fast_period: int = 12, 
                      slow_period: int = 26, 
                      signal_period: int = 9) -> Dict[str, List[float]]:
        """Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: List of price values
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
            
        Returns:
            Dictionary with MACD line, signal line, and histogram
        """
        if len(prices) < slow_period:
            nan_list = [np.nan] * len(prices)
            return {
                'macd': nan_list,
                'signal': nan_list,
                'histogram': nan_list
            }
        
        # Calculate EMAs
        fast_ema = self.calculate_ema(prices, fast_period)
        slow_ema = self.calculate_ema(prices, slow_period)
        
        # Calculate MACD line
        macd_line = []
        for i in range(len(prices)):
            if i < slow_period - 1:
                macd_line.append(np.nan)
            else:
                macd_line.append(fast_ema[i] - slow_ema[i])
        
        # Calculate signal line (EMA of MACD)
        macd_values = [x for x in macd_line if not np.isnan(x)]
        if len(macd_values) >= signal_period:
            signal_ema = self.calculate_ema(macd_values, signal_period)
            
            # Pad signal line with NaNs
            signal_line = [np.nan] * (len(macd_line) - len(signal_ema)) + signal_ema
        else:
            signal_line = [np.nan] * len(macd_line)
        
        # Calculate histogram
        histogram = []
        for i in range(len(macd_line)):
            if np.isnan(macd_line[i]) or np.isnan(signal_line[i]):
                histogram.append(np.nan)
            else:
                histogram.append(macd_line[i] - signal_line[i])
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def calculate_bollinger_bands(self, prices: List[float], 
                                 period: int = 20, 
                                 std_dev: float = 2.0) -> Dict[str, List[float]]:
        """Calculate Bollinger Bands.
        
        Args:
            prices: List of price values
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with upper band, middle band (SMA), and lower band
        """
        if len(prices) < period:
            nan_list = [np.nan] * len(prices)
            return {
                'upper': nan_list,
                'middle': nan_list,
                'lower': nan_list
            }
        
        # Calculate SMA (middle band)
        sma = self.calculate_sma(prices, period)
        
        # Calculate standard deviation
        upper_band = []
        lower_band = []
        
        for i in range(len(prices)):
            if i < period - 1:
                upper_band.append(np.nan)
                lower_band.append(np.nan)
            else:
                price_slice = prices[i - period + 1:i + 1]
                std = np.std(price_slice)
                
                upper_band.append(sma[i] + (std_dev * std))
                lower_band.append(sma[i] - (std_dev * std))
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    def calculate_volume_sma(self, volumes: List[float], period: int = 20) -> List[float]:
        """Calculate Volume Simple Moving Average.
        
        Args:
            volumes: List of volume values
            period: Moving average period
            
        Returns:
            List of volume SMA values
        """
        return self.calculate_sma(volumes, period)
    
    def calculate_price_volume_trend(self, prices: List[float], 
                                   volumes: List[float]) -> List[float]:
        """Calculate Price Volume Trend.
        
        Args:
            prices: List of price values
            volumes: List of volume values
            
        Returns:
            List of PVT values
        """
        if len(prices) != len(volumes) or len(prices) < 2:
            return [np.nan] * len(prices)
        
        pvt_values = [0]  # Start with 0
        
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                price_change_pct = (prices[i] - prices[i-1]) / prices[i-1]
                pvt = pvt_values[-1] + (volumes[i] * price_change_pct)
                pvt_values.append(pvt)
            else:
                pvt_values.append(pvt_values[-1])
        
        return pvt_values
    
    def calculate_stochastic_oscillator(self, highs: List[float], 
                                      lows: List[float], 
                                      closes: List[float], 
                                      k_period: int = 14, 
                                      d_period: int = 3) -> Dict[str, List[float]]:
        """Calculate Stochastic Oscillator.
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            k_period: %K period
            d_period: %D period
            
        Returns:
            Dictionary with %K and %D values
        """
        if len(highs) != len(lows) or len(lows) != len(closes) or len(closes) < k_period:
            nan_list = [np.nan] * len(closes)
            return {'k': nan_list, 'd': nan_list}
        
        k_values = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_values.append(np.nan)
            else:
                period_high = max(highs[i - k_period + 1:i + 1])
                period_low = min(lows[i - k_period + 1:i + 1])
                
                if period_high == period_low:
                    k = 50  # Avoid division by zero
                else:
                    k = ((closes[i] - period_low) / (period_high - period_low)) * 100
                
                k_values.append(k)
        
        # Calculate %D (SMA of %K)
        k_valid = [x for x in k_values if not np.isnan(x)]
        if len(k_valid) >= d_period:
            d_values = self.calculate_sma(k_valid, d_period)
            # Pad with NaNs
            d_padded = [np.nan] * (len(k_values) - len(d_values)) + d_values
        else:
            d_padded = [np.nan] * len(k_values)
        
        return {'k': k_values, 'd': d_padded}
    
    def calculate_all_indicators(self, historical_prices: List[HistoricalPrice]) -> Dict[str, List[float]]:
        """Calculate all technical indicators for given price data.
        
        Args:
            historical_prices: List of historical price data
            
        Returns:
            Dictionary with all calculated indicators
        """
        if not historical_prices:
            return {}
        
        # Sort by timestamp
        sorted_prices = sorted(historical_prices, key=lambda x: x.timestamp)
        
        # Extract price data (HistoricalPrice doesn't have OHLC, so simulate)
        closes = [float(p.price) for p in sorted_prices]
        # Simulate high/low as price +/- 1% for technical indicators
        highs = [price * 1.01 for price in closes]
        lows = [price * 0.99 for price in closes]
        volumes = [float(p.volume) if p.volume else 0 for p in sorted_prices]
        
        indicators = {}
        
        try:
            # Moving averages
            indicators['SMA_20'] = self.calculate_sma(closes, 20)
            indicators['SMA_50'] = self.calculate_sma(closes, 50)
            indicators['EMA_12'] = self.calculate_ema(closes, 12)
            indicators['EMA_26'] = self.calculate_ema(closes, 26)
            
            # Momentum indicators
            indicators['RSI'] = self.calculate_rsi(closes, 14)
            
            # MACD
            macd_data = self.calculate_macd(closes)
            indicators.update({
                'MACD': macd_data['macd'],
                'MACD_Signal': macd_data['signal'],
                'MACD_Histogram': macd_data['histogram']
            })
            
            # Bollinger Bands
            bb_data = self.calculate_bollinger_bands(closes)
            indicators.update({
                'BB_Upper': bb_data['upper'],
                'BB_Middle': bb_data['middle'],
                'BB_Lower': bb_data['lower']
            })
            
            # Volume indicators
            if any(v > 0 for v in volumes):
                indicators['Volume_SMA'] = self.calculate_volume_sma(volumes, 20)
                indicators['PVT'] = self.calculate_price_volume_trend(closes, volumes)
            
            # Stochastic Oscillator
            stoch_data = self.calculate_stochastic_oscillator(highs, lows, closes)
            indicators.update({
                'Stoch_K': stoch_data['k'],
                'Stoch_D': stoch_data['d']
            })
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
        
        return indicators
    
    def get_indicator_signals(self, indicators: Dict[str, List[float]]) -> Dict[str, str]:
        """Generate trading signals based on indicators.
        
        Args:
            indicators: Dictionary of calculated indicators
            
        Returns:
            Dictionary of signals for each indicator
        """
        signals = {}
        
        try:
            # RSI signals
            if 'RSI' in indicators and indicators['RSI']:
                latest_rsi = indicators['RSI'][-1]
                if not np.isnan(latest_rsi):
                    if latest_rsi > 70:
                        signals['RSI'] = 'OVERBOUGHT'
                    elif latest_rsi < 30:
                        signals['RSI'] = 'OVERSOLD'
                    else:
                        signals['RSI'] = 'NEUTRAL'
            
            # MACD signals
            if 'MACD' in indicators and 'MACD_Signal' in indicators:
                macd = indicators['MACD']
                signal = indicators['MACD_Signal']
                
                if len(macd) >= 2 and len(signal) >= 2:
                    if not np.isnan(macd[-1]) and not np.isnan(signal[-1]):
                        if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
                            signals['MACD'] = 'BULLISH_CROSSOVER'
                        elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
                            signals['MACD'] = 'BEARISH_CROSSOVER'
                        else:
                            signals['MACD'] = 'NEUTRAL'
            
            # Moving Average signals
            if 'SMA_20' in indicators and 'SMA_50' in indicators:
                sma20 = indicators['SMA_20']
                sma50 = indicators['SMA_50']
                
                if len(sma20) >= 2 and len(sma50) >= 2:
                    if not np.isnan(sma20[-1]) and not np.isnan(sma50[-1]):
                        if sma20[-1] > sma50[-1]:
                            signals['SMA_Cross'] = 'BULLISH'
                        else:
                            signals['SMA_Cross'] = 'BEARISH'
            
            # Stochastic signals
            if 'Stoch_K' in indicators and 'Stoch_D' in indicators:
                k = indicators['Stoch_K']
                d = indicators['Stoch_D']
                
                if len(k) >= 1 and len(d) >= 1:
                    if not np.isnan(k[-1]) and not np.isnan(d[-1]):
                        if k[-1] > 80 and d[-1] > 80:
                            signals['Stochastic'] = 'OVERBOUGHT'
                        elif k[-1] < 20 and d[-1] < 20:
                            signals['Stochastic'] = 'OVERSOLD'
                        else:
                            signals['Stochastic'] = 'NEUTRAL'
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
        
        return signals

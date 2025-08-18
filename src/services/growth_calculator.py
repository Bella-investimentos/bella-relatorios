# services/growth_calculator.py
import yfinance as yf
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GrowthCalculator:
    @staticmethod
    def calculate_cagr_10y(symbol: str) -> Optional[float]:
        """Calculate 10-year CAGR using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="10y", interval="1mo", auto_adjust=True)
            
            if not hist.empty and 'Close' in hist:
                first_price = float(hist['Close'].iloc[0])
                last_price = float(hist['Close'].iloc[-1])
                years = (hist.index[-1] - hist.index[0]).days / 365.25
                
                if first_price > 0 and years > 0:
                    return (last_price / first_price) ** (1 / years) - 1.0
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating CAGR for {symbol}: {e}")
            return None
# services/dividend_service.py
import requests
import pandas as pd
import yfinance as yf
from typing import Optional
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class DividendService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.FMP_API_KEY
    
    def get_dividend_yield(self, symbol: str, price: float) -> Optional[float]:
        """Get dividend yield, trying FMP first, then yfinance fallback"""
        if not price or price <= 0:
            return None
        
        # Try FMP first
        fmp_yield = self._get_dividend_yield_fmp(symbol, price)
        if fmp_yield is not None:
            return fmp_yield
        
        # Fallback to yfinance
        return self._get_dividend_yield_yfinance(symbol, price)
    
    def _get_dividend_yield_fmp(self, symbol: str, price: float) -> Optional[float]:
        """Get dividend yield from FMP"""
        if not self.api_key:
            return None
        
        try:
            # Try profile endpoint first
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
            response = requests.get(profile_url, params={"apikey": self.api_key}, timeout=10)
            
            if response.ok:
                data = response.json()
                if isinstance(data, list) and data:
                    ttm_yield = data[0].get("dividendYieldTTM")
                    if ttm_yield is not None:
                        return float(ttm_yield)
                    
                    last_div = data[0].get("lastDiv")
                    if last_div:
                        return float(last_div) / price
            
            # Try historical dividends endpoint
            div_url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{symbol}"
            response = requests.get(div_url, params={"apikey": self.api_key}, timeout=10)
            
            if response.ok:
                data = response.json()
                historical = data.get("historical") or data.get("historicalDividends", [])
                
                if historical:
                    df = pd.DataFrame(historical)
                    df["date"] = pd.to_datetime(df["date"])
                    cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)
                    recent_divs = df.loc[df["date"] >= cutoff, "dividend"].sum()
                    
                    if recent_divs > 0:
                        return float(recent_divs) / price
            
            return None
            
        except Exception as e:
            logger.debug(f"FMP dividend request failed for {symbol}: {e}")
            return None
    
    def _get_dividend_yield_yfinance(self, symbol: str, price: float) -> Optional[float]:
        """Fallback dividend yield using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            dividends = ticker.dividends
            
            if dividends is not None and not dividends.empty:
                cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)
                recent_divs = dividends[dividends.index >= cutoff].sum()
                
                if recent_divs > 0:
                    return float(recent_divs) / price
            
            return None
            
        except Exception as e:
            logger.debug(f"yfinance dividend fallback failed for {symbol}: {e}")
            return None
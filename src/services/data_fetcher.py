# services/data_fetcher.py
import requests
import pandas as pd
from typing import Optional, Dict, Any, List
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.FMP_API_KEY
        if not self.api_key:
            raise ValueError("FMP API key is required")
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """Fetch current price from FMP API"""
        try:
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}"
            params = {"apikey": self.api_key}
            
            response = requests.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list) and data:
                return data[0].get('price')
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    def fetch_historical_data(self, symbol: str, days: int = 260) -> List[Dict]:
        """Fetch historical data from FMP API"""
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
            params = {"timeseries": days, "apikey": self.api_key}
            
            response = requests.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            return data.get('historical', [])[::-1]  # Reverse for chronological order
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    def fetch_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Fetch company profile from FMP API"""
        try:
            url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
            params = {"apikey": self.api_key}
            
            response = requests.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list) and data:
                return data[0]
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching profile for {symbol}: {e}")
            return {}
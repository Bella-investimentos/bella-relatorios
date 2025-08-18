# services/asset_service.py
from typing import Optional, Dict, Any
import requests
from src.models.asset import Asset, AssetType
from src.services.data_fetcher import DataFetcher
from src.services.technical_analysis import TechnicalAnalysis
from src.services.dividend_service import DividendService
from src.services.growth_calculator import GrowthCalculator
from src.services.chart_generator import ChartGenerator
from src.config.settings import settings
import yfinance as yf
import logging
import os

logger = logging.getLogger(__name__)

class AssetService:
    def __init__(self, api_key: str = None):
        self.fmp_api_key = os.getenv('FMP_API_KEY')
        self.data_fetcher = DataFetcher(api_key)
        self.dividend_service = DividendService(api_key)
        self.growth_calculator = GrowthCalculator()
        self.chart_generator = ChartGenerator()
        self.technical_analysis = TechnicalAnalysis()
    
    def fetch_equity(self, symbol: str, quantity: float, is_etf: bool = False, 
                    antifragile: bool = False, target_price: Optional[float] = None) -> Optional[Asset]:
        """Fetch equity data and create Asset object"""
        try:
            # Fetch basic data
            price = self.data_fetcher.fetch_current_price(symbol)
            if not price:
                raise ValueError(f"Could not fetch price for {symbol}")
            
            profile = self.data_fetcher.fetch_company_profile(symbol)
            company_name = profile.get('companyName')
            sector = profile.get('sector')
            
            # Fallback to yfinance for name/sector if needed
            if not company_name or not sector:
                try:
                    yf_ticker = yf.Ticker(symbol)
                    info = yf_ticker.info
                    company_name = company_name or info.get('longName') or info.get('shortName')
                    sector = sector or info.get('sector')
                except Exception as e:
                    logger.debug(f"yfinance fallback failed for {symbol}: {e}")
            
            # Fetch historical data and calculate technical indicators
            historical_data = self.data_fetcher.fetch_historical_data(symbol)
            weekly_bars = self.technical_analysis.create_weekly_bars(historical_data)
            ema_20, ema_200 = self.technical_analysis.calculate_emas(weekly_bars)
            
            # Get dividend yield
            dividend_yield = self.dividend_service.get_dividend_yield(symbol, price)
            
            # Calculate growth
            cagr_10y = self.growth_calculator.calculate_cagr_10y(symbol)
            average_growth = round(cagr_10y * 100, 1) if cagr_10y else None
            
            # Generate chart
            chart_path = self.chart_generator.generate_weekly_chart(symbol, weekly_bars, target_price)
            
            # Calculate antifragile entry price if needed
            antifragile_entry_price = None
            if is_etf and antifragile:
                antifragile_entry_price = round(price * settings.ANTIFRAGILE_MULTIPLIER, 4)
            
            return Asset(
                symbol=symbol,
                asset_type=AssetType.ETF if is_etf else AssetType.STOCK,
                unit_price=price,
                quantity=quantity,
                company_name=company_name,
                sector=sector,
                dividend_yield=dividend_yield,
                target_price=target_price,
                ema_20=ema_20,
                ema_200=ema_200,
                average_growth=average_growth,
                chart_path=chart_path,
                antifragile_entry_price=antifragile_entry_price
            )
            
        except Exception as e:
            logger.error(f"Error fetching equity {symbol}: {e}")
            return None
    
    def fetch_crypto(self, symbol: str, quantity: float = 0.0, company_name: Optional[str] = None, expected_growth: Optional[float] = None) -> Optional[Asset]:
        """Fetch crypto data for any symbol - tries FMP first, then yfinance as fallback"""
        try:
            # Primeiro tenta buscar na FMP
            unit_price = self._fetch_crypto_from_fmp(symbol)
            
            # Se não conseguir na FMP, usa yfinance como fallback
            if unit_price is None:
                unit_price = self._fetch_crypto_from_yfinance(symbol)
            
            # Se nenhuma das duas funcionou
            if unit_price is None:
                raise ValueError(f"No price data found for {symbol} in any source")

            return Asset(
                symbol=symbol.upper(),
                asset_type=AssetType.CRYPTO,
                unit_price=unit_price,
                quantity=quantity,
                company_name=company_name if company_name else symbol.upper(),
                sector="Crypto",
                dividend_yield=0.0,
                target_price=None,
                average_growth=expected_growth,
                
            )
        except Exception as e:
            logger.error(f"Error fetching crypto {symbol}: {e}")
            return None

    def _fetch_crypto_from_fmp(self, symbol: str) -> Optional[float]:
        """Fetch crypto price from FMP API"""
        try:
            # Para crypto na FMP, o formato geralmente é diferente
            # Alguns símbolos comuns: BTCUSD, ETHUSD, etc.
            fmp_symbol = symbol.replace('-', '').replace('USD', 'USD')
            
            url = f"https://financialmodelingprep.com/api/v3/quote/{fmp_symbol}"
            params = {"apikey": self.fmp_api_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0 and 'price' in data[0]:
                price = float(data[0]['price'])
                logger.info(f"Successfully fetched {symbol} price from FMP: ${price}")
                return price
            else:
                logger.warning(f"No price data in FMP response for {symbol}")
                return None
                
        except Exception as e:
            logger.warning(f"FMP fetch failed for {symbol}: {e}")
            return None

    def _fetch_crypto_from_yfinance(self, symbol: str) -> Optional[float]:
        """Fetch crypto price from yfinance as fallback"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Tenta diferentes períodos se o primeiro falhar
            for period in ["2d", "5d", "1mo"]:
                try:
                    hist = ticker.history(period=period, interval="1d", auto_adjust=True)
                    if hist is not None and not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                        logger.info(f"Successfully fetched {symbol} price from yfinance: ${price}")
                        return price
                except Exception as period_error:
                    logger.debug(f"Period {period} failed for {symbol}: {period_error}")
                    continue
            
            logger.warning(f"No valid data found in yfinance for {symbol}")
            return None
            
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {symbol}: {e}")
            return None
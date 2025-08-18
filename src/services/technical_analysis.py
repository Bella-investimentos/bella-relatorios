# services/technical_analysis.py
import pandas as pd
from typing import Tuple, Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TechnicalAnalysis:
    @staticmethod
    def create_weekly_bars(daily_data: List[Dict]) -> List[object]:
        """Convert daily data to weekly bars"""
        if not daily_data:
            return []
        
        try:
            df_daily = pd.DataFrame(daily_data)
            df_daily['date'] = pd.to_datetime(df_daily['date'])
            df_daily = df_daily.set_index('date').sort_index()
            
            weekly_bars = []
            for week_start, week_data in df_daily.groupby(pd.Grouper(freq='W')):
                if not week_data.empty:
                    bar = type('Bar', (), {
                        'open': week_data['open'].iloc[0],
                        'high': week_data['high'].max(),
                        'low': week_data['low'].min(),
                        'close': week_data['close'].iloc[-1],
                        'volume': week_data['volume'].sum(),
                        'date': week_data.index[-1].strftime('%Y-%m-%d')
                    })()
                    weekly_bars.append(bar)
            
            return weekly_bars
            
        except Exception as e:
            logger.error(f"Error creating weekly bars: {e}")
            return []
    
    @staticmethod
    def calculate_emas(bars: List[object]) -> Tuple[Optional[float], Optional[float]]:
        """Calculate EMA20 and EMA200"""
        if not bars or len(bars) < 20:
            return None, None
        
        try:
            df = pd.DataFrame([{'date': bar.date, 'close': bar.close} for bar in bars])
            df.set_index('date', inplace=True)
            
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
            ema_20 = float(df['ema_20'].iloc[-1])
            
            ema_200 = None
            if len(bars) >= 200:
                df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
                ema_200 = float(df['ema_200'].iloc[-1])
            
            return ema_20, ema_200
            
        except Exception as e:
            logger.error(f"Error calculating EMAs: {e}")
            return None, None
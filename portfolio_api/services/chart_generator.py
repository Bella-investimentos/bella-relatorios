# services/chart_generator.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import os
from typing import Optional, List
from portfolio_api.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class ChartGenerator:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or settings.CHART_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_weekly_chart(self, symbol: str, weekly_bars: List[object], 
                            target_price: Optional[float] = None) -> Optional[str]:
        """Generate weekly technical analysis chart"""
        if not weekly_bars or len(weekly_bars) < 20:
            logger.warning(f"Insufficient weekly data for {symbol} (min. 20 candles)")
            return None
        
        try:
            # Create DataFrame
            df = pd.DataFrame([{'date': b.date, 'close': b.close} for b in weekly_bars])
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            # Calculate EMAs
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
            if len(df) >= 200:
                df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
            
            # Create chart
            plt.figure(figsize=(10, 5))
            
            # Price line
            current_price = df['close'].iloc[-1]
            plt.plot(df.index, df['close'], label=f'Preço Atual: ${current_price:.2f}',
                    linewidth=2.5, color='#2E86AB')
            
            # Target price line
            if target_price:
                plt.axhline(y=target_price, color='#C73E1D', linestyle='-.',
                           linewidth=2, label=f'Preço alvo: ${target_price:.2f}')
            
            # EMA lines
            ema_20_value = df['ema_20'].iloc[-1]
            plt.plot(df.index, df['ema_20'], label=f'Entrada Ideal: ${ema_20_value:.2f}',
                    linestyle='--', linewidth=2, color='#A23B72')
            
            if 'ema_200' in df.columns:
                ema_200_value = df['ema_200'].iloc[-1]
                plt.plot(df.index, df['ema_200'], label=f'Preço de suporte: ${ema_200_value:.2f}',
                        linestyle=':', linewidth=2, color='#F18F01')
            
            # Chart formatting
            plt.title(f'Análise Técnica - {symbol}', fontsize=14, fontweight='bold')
            ax = plt.gca()
            ax.set_xlabel('Período', fontsize=12)
            ax.set_ylabel('Preço (USD)', fontsize=12)
            
            plt.legend(loc='upper left', frameon=True, fancybox=True,
                      shadow=True, fontsize=10, bbox_to_anchor=(0.02, 0.98))
            
            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            ax.tick_params(axis='y', which='both', labelleft=True, labelright=True, 
                          left=True, right=True)
            ax.yaxis.set_ticks_position('both')
            
            # Right axis
            ax_r = ax.twinx()
            ax_r.set_ylim(ax.get_ylim())
            ax_r.set_yticks(ax.get_yticks())
            ax_r.set_ylabel('Preço (USD)', fontsize=12)
            ax_r.grid(False)
            
            # Save chart
            chart_path = os.path.join(self.output_dir, f"chart_{symbol}.png")
            plt.tight_layout()
            plt.savefig(chart_path)
            plt.close()
            
            return os.path.abspath(chart_path)
            
        except Exception as e:
            logger.error(f"Error generating chart for {symbol}: {e}")
            return None
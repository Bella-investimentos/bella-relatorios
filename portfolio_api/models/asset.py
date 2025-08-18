# models/asset.py
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class AssetType(Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    REAL_ESTATE = "REAL_ESTATE"
    BOND = "BOND"

@dataclass
class Asset:
    symbol: str
    asset_type: AssetType
    unit_price: float
    quantity: float
    company_name: Optional[str] = None
    sector: Optional[str] = None
    dividend_yield: Optional[float] = None
    target_price: Optional[float] = None
    ema_20: Optional[float] = None
    ema_200: Optional[float] = None
    average_growth: Optional[float] = None
    chart_path: Optional[str] = None
    antifragile_entry_price: Optional[float] = None
    
    @property
    def investment(self) -> float:
        return self.unit_price * self.quantity

@dataclass
class Bond:
    name: str
    code: str
    maturity: str
    unit_price: float
    quantity: float
    coupon: float
    description: list

    @property
    def investment(self) -> float:
        return self.unit_price * self.quantity
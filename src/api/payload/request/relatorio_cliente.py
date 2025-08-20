from pydantic import BaseModel, Field
from typing import List, Optional


class BondIn(BaseModel):
    name: str
    code: str
    maturity: str           # YYYY-MM-DD
    unit_price: float
    quantity: float
    coupon: float
    description: List[str] = Field(default_factory=list)

class EquityIn(BaseModel):
    symbol: str
    quantity: float
    target_price: Optional[float] = None

class CryptoIn(BaseModel):
    symbol: str
    quantity: float
    company_name: Optional[str] = None
    expected_growth: Optional[float] = None

class RealEstateIn(BaseModel):
    name: str
    invested_value: float
    appreciation: float

class ClienteRelatorioPayload(BaseModel):
    investor: str
    bonds: List[BondIn] = Field(default_factory=list)
    stocks: List[EquityIn] = Field(default_factory=list)
    opp_stocks: List[EquityIn] = Field(default_factory=list)
    etfs: List[EquityIn] = Field(default_factory=list)
    etfs_op: List[EquityIn] = Field(default_factory=list)
    etfs_af: List[EquityIn] = Field(default_factory=list)
    cryptos: List[CryptoIn] = Field(default_factory=list)
    real_estates: List[RealEstateIn] = Field(default_factory=list)
    user_id: Optional[str] = None
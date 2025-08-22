from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class BondData(BaseModel):
    name: str
    code: str
    maturity: str
    unit_price: float
    coupon: float
    quantity: int
    investment: float
    description: List[str] = []

class ReportRequest(BaseModel):
    investor: str
    total_value: Optional[float] = None
    bonds: Optional[List[Dict[str, Any]]] = []
    stock_symbols: Optional[List[str]] = []
    opp_stock_symbols: Optional[List[str]] = []
    etf_symbols: Optional[List[str]] = []

class ReportResponse(BaseModel):
    success: bool
    message: str
    pdf_url: Optional[str] = None
    html_content: Optional[str] = None
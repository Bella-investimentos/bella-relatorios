# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from src.services.asset_service import AssetService
from src.models.asset import Asset
import logging
from mangum import Mangum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Portfolio API", version="1.0.0")

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
asset_service = AssetService()

# Request/Response models
class EquityRequest(BaseModel):
    symbol: str
    quantity: float
    is_etf: bool = False
    antifragile: bool = False
    target_price: Optional[float] = None

class CryptoRequest(BaseModel):
    symbol: str
    quantity: float
    company_name: Optional[str] = None
    expected_growth: Optional[float] = None
    
class AssetResponse(BaseModel):
    symbol: str
    asset_type: str
    unit_price: float
    quantity: float
    investment: float
    company_name: Optional[str] = None
    sector: Optional[str] = None
    dividend_yield: Optional[float] = None
    target_price: Optional[float] = None
    ema_20: Optional[float] = None
    ema_200: Optional[float] = None
    average_growth: Optional[float] = None
    chart_path: Optional[str] = None
    antifragile_entry_price: Optional[float] = None

@app.get("/")
def root():
    return {"message": "Portfolio API is running"}

@app.post("/api/equity", response_model=AssetResponse)
def fetch_equity(request: EquityRequest):
    """Fetch equity (stock/ETF) data"""
    try:
        asset = asset_service.fetch_equity(
            symbol=request.symbol,
            quantity=request.quantity,
            is_etf=request.is_etf,
            antifragile=request.antifragile,
            target_price=request.target_price
        )
        
        if not asset:
            raise HTTPException(status_code=404, detail=f"Could not fetch data for {request.symbol}")
        
        return AssetResponse(
            symbol=asset.symbol,
            asset_type=asset.asset_type.value,
            unit_price=asset.unit_price,
            quantity=asset.quantity,
            investment=asset.investment,
            company_name=asset.company_name,
            sector=asset.sector,
            dividend_yield=asset.dividend_yield,
            target_price=asset.target_price,
            ema_20=asset.ema_20,
            ema_200=asset.ema_200,
            average_growth=asset.average_growth,
            chart_path=asset.chart_path,
            antifragile_entry_price=asset.antifragile_entry_price
        )
        
    except Exception as e:
        logger.error(f"Error fetching equity {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/crypto", response_model=AssetResponse)
def fetch_crypto(request: CryptoRequest):
    """Fetch crypto data for any symbol"""
    try:
        asset = asset_service.fetch_crypto(
            symbol=request.symbol,
            quantity=request.quantity,
            company_name=request.company_name,
            expected_growth=request.expected_growth
        )
        
        if not asset:
            raise HTTPException(status_code=404, detail=f"Could not fetch data for {request.symbol}")
        
        return AssetResponse(
            symbol=asset.symbol,
            asset_type=asset.asset_type.value,
            unit_price=asset.unit_price,
            quantity=asset.quantity,
            investment=asset.investment,
            company_name=asset.company_name,
            sector=asset.sector,
            dividend_yield=asset.dividend_yield,
            target_price=asset.target_price,
            ema_20=asset.ema_20,
            ema_200=asset.ema_200,
            average_growth=asset.average_growth,
            chart_path=asset.chart_path
        )
        
    except Exception as e:
        logger.error(f"Error fetching crypto {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API is running properly"}


handler = Mangum(app, lifespan="off")
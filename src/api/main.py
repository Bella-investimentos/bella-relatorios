from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import logging
import os
from typing import Dict, Any
from io import BytesIO
from mangum import Mangum

from src.api.payload.request.relatorio_cliente import ClienteRelatorioPayload
from src.services.carteiras.make_report import build_report_from_payload
from src.services.carteiras.assembleia_report import build_report_assembleia_from_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Portfolio API", version="1.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API is running properly - Version 1.0.2"}

def _stream_pdf(buf: BytesIO, filename: str, disposition: str = "attachment"):
    """disposition: 'attachment' (download) ou 'inline' (abrir no navegador)."""
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'}
    )

# === Assembleia ===
@app.post("/generate-report/assembleia")
def generate_report_assembleia(
    payload: Dict[str, Any],  # <--- em vez de ClienteRelatorioPayload
    symbol: str | None = Query(default=None)
):
    if symbol and not os.getenv("FMP_API_KEY"):
        raise HTTPException(status_code=400, detail="FMP_API_KEY não definida no ambiente.")

    try:
        buf = build_report_assembleia_from_payload(payload, selected_symbol=symbol)  # passa o dict cru
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF (assembleia): {e}")

    return _stream_pdf(buf, "Assembleia_Investidores.pdf")
   

# === Relatório genérico ===
@app.post("/generate-report")
def generate_report_generic(payload: ClienteRelatorioPayload):
    buf = build_report_from_payload(payload.dict())
    return _stream_pdf(buf, "Relatorio_Carteira.pdf", disposition="attachment")

# Lambda
handler = Mangum(app, lifespan="off")

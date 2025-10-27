

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from typing import Dict, Any
from io import BytesIO
from mangum import Mangum
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.api.payload.request.relatorio_cliente import ClienteRelatorioPayload
from src.services.carteiras.make_report import build_report_from_payload
from src.services.carteiras.assembleia_report import build_report_assembleia_from_payload
from src.services.s3.aws_s3_service import generate_temporary_url, upload_bytes_to_s3
from src.services.carteiras.assembleia.constants import NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Portfolio API", version="1.4.0")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Thread pool para tarefas CPU-bound
executor = ThreadPoolExecutor(max_workers=4)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache simples em memória (para Lambda: use Redis/ElastiCache em produção)
report_cache: Dict[str, Dict[str, Any]] = {}

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API v1.4.0 - Optimized"}


# === Assembleia ===
async def _generate_and_upload_assembleia(payload: Dict[str, Any], symbol: str | None):
    """Função assíncrona para gerar relatório em background"""
    try:
        loop = asyncio.get_event_loop()
        buf = await loop.run_in_executor(
            executor,
            build_report_assembleia_from_payload,
            payload,
            symbol
        )
        if buf:
            await loop.run_in_executor(
                executor,
                upload_bytes_to_s3,
                buf,
                NOME_RELATORIO_ASSEMBLEIA,
                BUCKET_RELATORIOS,
                "application/pdf" 
            )
            logger.info(f"Relatório assembleia gerado: {symbol}")
    except Exception as e:
        logger.error(f"Erro ao gerar relatório assembleia: {e}")


@app.post("/generate-report/assembleia")
async def generate_assembleia_post(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """POST: Inicia geração em background"""
    required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
    missing = [e for e in required_envs if not os.getenv(e)]
    if missing:
        raise HTTPException(400, f"Variáveis faltando: {', '.join(missing)}")
    
    symbol = payload.get("symbol")
    background_tasks.add_task(_generate_and_upload_assembleia, payload, symbol)
    
    return {"message": "Relatório assembleia em processamento", "status": "processing"}


@app.get("/download/assembleia")
def download_assembleia():
    """GET: Retorna URL temporária do último relatório"""
    required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
    missing = [e for e in required_envs if not os.getenv(e)]
    if missing:
        raise HTTPException(400, f"Variáveis faltando: {', '.join(missing)}")
    
    url = generate_temporary_url(NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS)
    return {"url": url, "status": "ready"}






# === Relatório Genérico ===
@app.post("/generate-report")
async def generate_generic_report(payload: ClienteRelatorioPayload):
    """Relatório genérico síncrono (rápido)"""
    try:
        loop = asyncio.get_event_loop()
        buf = await loop.run_in_executor(
            executor,
            build_report_from_payload,
            payload.dict()
        )
        
        # Retorna PDF diretamente
        from fastapi.responses import StreamingResponse
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Relatorio_Carteira.pdf"'}
        )
    except Exception as e:
        logger.error(f"Erro ao gerar relatório genérico: {e}")
        raise HTTPException(500, f"Erro: {str(e)}")


# Lambda handler
handler = Mangum(app, lifespan="off")
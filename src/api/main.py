from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
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
from src.services.s3.aws_s3_service import generate_temporary_url


from src.services.carteiras.assembleia.constants import NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Portfolio API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API is running properly - Version 1.2.0"}

def _stream_pdf(buf: BytesIO, filename: str, disposition: str = "attachment"):
    """disposition: 'attachment' (download) ou 'inline' (abrir no navegador)."""
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'}
    )

# === Assembleia ===
def _generate_and_upload(payload: Dict[str, Any], symbol: str | None):
    try:
        # Gera o relatório (bloqueante) em background
        buf = build_report_assembleia_from_payload(payload, selected_symbol=symbol)
        if buf:
            upload_pdf_to_s3(buf, "relatorio-assembleia.pdf", "bella-relatorios")
    except Exception as e:
        # Aqui você pode logar o erro
        import logging
        logging.error("Erro ao gerar relatório assembleia: %s", e)

@app.post("/generate-report/assembleia")
def generate_report_assembleia(
    payload: Dict[str, Any],
    symbol: str | None = Query(default=None),
    background_tasks: BackgroundTasks = None
):
    required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
    missing = [env for env in required_envs if not os.getenv(env)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"As seguintes variáveis de ambiente não estão definidas: {', '.join(missing)}"
        )

    # Adiciona a tarefa para rodar em background
    background_tasks.add_task(_generate_and_upload, payload, symbol)

    # Retorna imediatamente
    return {"message": "Relatório em processamento"}

@app.get("/download/assembleia")
def generate_report_assembleia():
    required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
    missing = [env for env in required_envs if not os.getenv(env)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"As seguintes variáveis de ambiente não estão definidas: {', '.join(missing)}"
        )

    # Adiciona a tarefa para rodar em background
    url = generate_temporary_url(NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS)

    # Retorna imediatamente
    return {"url": url}

   

# === Relatório genérico ===
@app.post("/generate-report")
def generate_report_generic(payload: ClienteRelatorioPayload):
    print("Payload recebido:", payload.dict())
    buf = build_report_from_payload(payload.dict())
    return _stream_pdf(buf, "Relatorio_Carteira.pdf", disposition="attachment")

# Lambda
handler = Mangum(app, lifespan="off")

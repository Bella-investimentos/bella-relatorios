# from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse, JSONResponse
# import logging
# import os
# from typing import Dict, Any
# from io import BytesIO
# from mangum import Mangum
# from pathlib import Path
# from datetime import datetime
# from src.api.payload.request.relatorio_cliente import ClienteRelatorioPayload
# from src.services.carteiras.make_report import build_report_from_payload
# from src.services.carteiras.assembleia_report import build_report_assembleia_from_payload
# from src.services.s3.aws_s3_service import generate_temporary_url
# from src.services.carteiras.selecaoAtivos_report import generate_selecaoAtivos_report
# from src.services.s3.aws_s3_service import upload_bytes_to_s3
# from src.services.carteiras.assembleia.constants import NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI(title="Portfolio API", version="1.3.0")
# XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
# def _normalize_excel_result(result) -> tuple[BytesIO, str]:
#     """
#     Aceita:
#       - BytesIO
#       - (BytesIO, filename)
#       - caminho str/Path
#     Retorna: (buf, filename)
#     """
#     ts = datetime.now().strftime("%Y%m%d-%H%M%S")
#     default_name = f"selecao_ativos_{ts}.xlsx"

#     if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], BytesIO):
#         buf, filename = result
#         return buf, (filename or default_name)

#     if isinstance(result, BytesIO):
#         return result, default_name

#     if isinstance(result, (str, Path)):
#         p = Path(result)
#         with open(p, "rb") as f:
#             data = f.read()
#         return BytesIO(data), p.name

#     raise ValueError("Retorno inesperado de generate_selecaoAtivos_report()")


# @app.get("/api/health")
# def health_check():
#     return {"status": "healthy", "message": "API is running properly - Version 1.2.0"}

# def _stream_pdf(buf: BytesIO, filename: str, disposition: str = "attachment"):
#     """disposition: 'attachment' (download) ou 'inline' (abrir no navegador)."""
#     buf.seek(0)
#     return StreamingResponse(
#         buf,
#         media_type="application/pdf",
#         headers={"Content-Disposition": f'{disposition}; filename="{filename}"'}
#     )

# # === Assembleia ===
# def _generate_and_upload(payload: Dict[str, Any], symbol: str | None):
#     try:
#         # Gera o relatório (bloqueante) em background
#         buf = build_report_assembleia_from_payload(payload, selected_symbol=symbol)
#         if buf:
#             upload_pdf_to_s3(buf, "relatorio-assembleia.pdf", "bella-relatorios")
#     except Exception as e:
#         # Aqui você pode logar o erro
#         import logging
#         logging.error("Erro ao gerar relatório assembleia: %s", e)

# @app.post("/generate-report/assembleia")
# def generate_report_assembleia(
#     payload: Dict[str, Any],
#     symbol: str | None = Query(default=None),
#     background_tasks: BackgroundTasks = None
# ):
#     required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
#     missing = [env for env in required_envs if not os.getenv(env)]
#     if missing:
#         raise HTTPException(
#             status_code=400,
#             detail=f"As seguintes variáveis de ambiente não estão definidas: {', '.join(missing)}"
#         )

#     # Adiciona a tarefa para rodar em background
#     background_tasks.add_task(_generate_and_upload, payload, symbol)

#     # Retorna imediatamente
#     return {"message": "Relatório em processamento"}

# @app.get("/download/assembleia")
# def generate_report_assembleia():
#     required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
#     missing = [env for env in required_envs if not os.getenv(env)]
#     if missing:
#         raise HTTPException(
#             status_code=400,
#             detail=f"As seguintes variáveis de ambiente não estão definidas: {', '.join(missing)}"
#         )

#     # Adiciona a tarefa para rodar em background
#     url = generate_temporary_url(NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS)

#     # Retorna imediatamente
#     return {"url": url}

# # === Seleção de Ativos ===
# @app.post("/generate-report/selecao-ativos")
# def generate_report_selecao_ativos():
#     required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
#     missing = [env for env in required_envs if not os.getenv(env)]
#     if missing:
#         raise HTTPException(
#             status_code=400,
#             detail=f"As seguintes variáveis de ambiente não estão definidas: {', '.join(missing)}"
#         )

#     try:
#         # 1) Gera o Excel (sua função atual)
#         result = generate_selecaoAtivos_report()

#         # 2) Normaliza para (BytesIO, filename)
#         buf, filename = _normalize_excel_result(result)

#         # 3) Define a chave no bucket
#         key = f"selecao-ativos/{filename}"

#         # 4) Upload para S3 com content-type de Excel
#         upload_bytes_to_s3(
#             buffer=buf,
#             key=key,
#             bucket=BUCKET_RELATORIOS,
#             content_type=XLSX_MIME
#         )

#         # 5) URL temporária (presigned)
#         url = generate_temporary_url(key, BUCKET_RELATORIOS)

#         return JSONResponse({"status": "ok", "key": key, "url": url})

#     except Exception as e:
#         logger.error(f"Erro ao gerar/enviar relatório de seleção de ativos: {e}")
#         raise HTTPException(status_code=500, detail="Erro ao gerar relatório de seleção de ativos")
   

# # === Relatório genérico ===
# @app.post("/generate-report")
# def generate_report_generic(payload: ClienteRelatorioPayload):
#     print("Payload recebido:", payload.dict())
#     buf = build_report_from_payload(payload.dict())
#     return _stream_pdf(buf, "Relatorio_Carteira.pdf", disposition="attachment")

# # Lambda
# handler = Mangum(app, lifespan="off")

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
from src.services.carteiras.selecaoAtivos_report import generate_selecaoAtivos_report
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
                BUCKET_RELATORIOS
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


# === Seleção de Ativos - OTIMIZADO ===
async def _generate_selecao_async():
    """Gera o relatório de forma assíncrona"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, generate_selecaoAtivos_report)
    return result


@app.post("/generate-report/selecao-ativos")
async def generate_selecao_ativos(background_tasks: BackgroundTasks):
    """
    Inicia geração em background e retorna job_id.
    Cliente pode consultar status via GET /status/selecao-ativos/{job_id}
    """
    required_envs = ["FMP_API_KEY", "AWS_KEY", "AWS_SECRET"]
    missing = [e for e in required_envs if not os.getenv(e)]
    if missing:
        raise HTTPException(400, f"Variáveis faltando: {', '.join(missing)}")
    
    job_id = f"selecao_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Inicia processamento em background
    background_tasks.add_task(_process_selecao_report, job_id)
    
    return JSONResponse({
        "status": "processing",
        "job_id": job_id,
        "message": "Relatório em processamento. Use GET /status/selecao-ativos/{job_id} para verificar"
    })


async def _process_selecao_report(job_id: str):
    """Processa o relatório e faz upload"""
    try:
        report_cache[job_id] = {"status": "processing", "progress": 0}
        
        # Gera relatório
        result = await _generate_selecao_async()
        
        # Normaliza resultado
        if isinstance(result, str):
            # É um caminho de arquivo
            with open(result, "rb") as f:
                buf = BytesIO(f.read())
            filename = os.path.basename(result)
        elif isinstance(result, BytesIO):
            buf = result
            filename = f"selecao_ativos_{job_id}.xlsx"
        else:
            raise ValueError("Formato inesperado de retorno")
        
        report_cache[job_id]["progress"] = 50
        
        # Upload para S3
        key = f"selecao-ativos/{filename}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            upload_bytes_to_s3,
            buf,
            key,
            BUCKET_RELATORIOS,
            XLSX_MIME
        )
        
        # Gera URL
        url = generate_temporary_url(key, BUCKET_RELATORIOS)
        
        report_cache[job_id] = {
            "status": "completed",
            "progress": 100,
            "url": url,
            "key": key
        }
        
        logger.info(f"Relatório {job_id} concluído: {key}")
        
    except Exception as e:
        logger.error(f"Erro ao processar {job_id}: {e}")
        report_cache[job_id] = {
            "status": "error",
            "progress": 0,
            "error": str(e)
        }


@app.get("/status/selecao-ativos/{job_id}")
def get_selecao_status(job_id: str):
    """Consulta status do relatório"""
    if job_id not in report_cache:
        raise HTTPException(404, "Job não encontrado")
    
    return JSONResponse(report_cache[job_id])


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
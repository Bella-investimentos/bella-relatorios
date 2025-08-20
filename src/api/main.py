from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import logging
from io import BytesIO
from mangum import Mangum
from src.api.payload.request.relatorio_cliente import ClienteRelatorioPayload
from src.services.carteiras.make_report import build_report_from_payload

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

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API is running properly"}

@app.post("/generate-report")
def generate_report(payload: ClienteRelatorioPayload):
    pdf_bytes = build_report_from_payload(payload.dict())
    pdf_buffer = BytesIO(pdf_bytes)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Relatorio_Carteira.pdf"}
    )

handler = Mangum(app, lifespan="off")
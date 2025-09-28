from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from .constants import ETF_PAGE_BG_IMG  # fundo é desenhado no onPage
from .utils import (
    normalize_asset_minimal,
    draw_asset_logo_rounded,
    wrap_and_draw,
    draw_justified_paragraph,
    JUSTIFIED_WHITE,
)

# Layout conforme seu snippet (logo 550, título 605, subtítulo 550)
SPEC = {
    "bg": ETF_PAGE_BG_IMG,  # opcional (não usamos aqui)
    "logo":     {"x": 60,  "y": 500, "w": 75,  "h": 75},
    "title":    {"x": 140, "y": 555, "w": 420, "lh": 30, "font": ("Helvetica-Bold", 26), "max_lines": 2},
    "subtitle": {"x": 140, "y": 500, "font": ("Helvetica-Bold", 16)},  # linha azul
    "text":     {"x": 60,  "y": 70,  "w": 490, "h": 390},
}

def draw_text_asset_page(c: Canvas, data: dict):
    """
    Desenha logo + título + subtítulo "Troca da semana" e o texto livre.
    O fundo (Fundo_geral.png) deve ser pintado no onPage.
    """
    spec = SPEC

    # --- Nome e símbolo (com fallbacks)
    try:
        ent = normalize_asset_minimal(data) or {}
    except Exception:
        ent = {}
    symbol  = (ent.get("symbol") or data.get("symbol") or "").strip().upper()
    company = (
        ent.get("company_name")
        or ent.get("name")
        or data.get("company_name")
        or data.get("name")
        or symbol
    )

    # --- Logo (com placeholder se não houver)
    try:
        ok = draw_asset_logo_rounded(
            c, data,
            spec["logo"]["x"], spec["logo"]["y"],
            spec["logo"]["w"], spec["logo"]["h"],
            radius=8, draw_stroke=True, stroke_width=1.0
        )
        if not ok:
            c.setFillColorRGB(0.9, 0.9, 0.9)
            c.rect(spec["logo"]["x"], spec["logo"]["y"], spec["logo"]["w"], spec["logo"]["h"], stroke=0, fill=1)
    except Exception as e:
        print(f"[text-asset] logo: {e}")
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(spec["logo"]["x"], spec["logo"]["y"], spec["logo"]["w"], spec["logo"]["h"], stroke=0, fill=1)

    # --- TÍTULO (Nome + Ticker) em branco
    try:
        c.setFillColorRGB(1, 1, 1)
        wrap_and_draw(
            c, f"{company} ({symbol})".strip(),
            spec["title"]["x"], spec["title"]["y"],
            spec["title"]["w"], spec["title"]["lh"],
            spec["title"]["font"], spec["title"]["max_lines"]
        )
    except Exception as e:
        print(f"[text-asset] title: {e}")
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(spec["title"]["x"], spec["title"]["y"], f"{company} ({symbol})")

    # --- SUBTÍTULO fixo em azul
    try:
        c.setFillColorRGB(0.20, 0.49, 0.87)
        c.setFont(*spec["subtitle"]["font"])
        c.drawString(spec["subtitle"]["x"], spec["subtitle"]["y"], "Troca da semana")
    except Exception as e:
        print(f"[text-asset] subtitle: {e}")

    # --- TEXTO (corpo) justificado em branco
    try:
        texto = (data.get("text") or data.get("note") or "").strip() or "— Texto não informado —"
        draw_justified_paragraph(
            c, texto,
            spec["text"]["x"], spec["text"]["y"], spec["text"]["w"], spec["text"]["h"],
            JUSTIFIED_WHITE
        )
    except Exception as e:
        print(f"[text-asset] paragraph: {e}")
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(spec["text"]["x"], spec["text"]["y"], "Falha ao renderizar o texto deste item.")

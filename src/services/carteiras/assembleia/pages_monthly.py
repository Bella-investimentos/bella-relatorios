# src/services/carteiras/assembleia/pages_monthly.py
from __future__ import annotations
from typing import Dict, Any, List
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from .constants import img_path, ETF_PAGE_BG_IMG   # use o BG que preferir
from .utils import fmt_currency_usd, wrap_and_draw

TITLE_FONT    = ("Helvetica-Bold", 26)
SUBTITLE_FONT = ("Helvetica-Bold", 14)
HEADER_FONT   = ("Helvetica-Bold", 11)
ROW_FONT      = ("Helvetica", 10)

def _colspec():
    """
    Retorna (x0, total_w, [larguras das 4 cols]).
    Colunas: [Ativo] [1ª sexta] [Sexta atual] [Variação]
    """
    x0 = 60
    total_w = 490
    # ajuste fino aqui se quiser
    c1 = 250   # Ativo
    c2 = 90    # 1ª sexta
    c3 = 90    # Sexta atual
    c4 = 60    # %
    assert c1 + c2 + c3 + c4 <= total_w
    return x0, total_w, [c1, c2, c3, c4]

def draw_monthly_summary_page(c: Canvas, page: Dict[str, Any]):
    """
    Espera page={"rows":[{symbol, company_name, p0, p1, chg}], "label": "Setembro/2025"}.
    """
    rows: List[Dict[str, Any]] = page.get("rows", [])
    month_label: str = page.get("label", "")

    w, h = A4
    # fundo
    try:
        c.drawImage(img_path(ETF_PAGE_BG_IMG), 0, 0, width=w, height=h)
    except Exception:
        pass

    # Título
    c.setFillColorRGB(1, 1, 1)
    c.setFont(*TITLE_FONT)
    c.drawString(60, 720, "Resumo mensal da carteira")

    c.setFont(*SUBTITLE_FONT)
    c.setFillColorRGB(0.20, 0.49, 0.87)
    c.drawString(60, 690, f"Período: {month_label}")

    # Tabela
    x0, total_w, cols = _colspec()
    y = 660  # topo da tabela
    row_h = 22
    pad_x = 6

    # Cabeçalho
    c.setFillColorRGB(0.10, 0.10, 0.10)
    c.roundRect(x0, y - row_h, total_w, row_h, 6, stroke=0, fill=1)

    c.setFillColorRGB(1, 1, 1)
    c.setFont(*HEADER_FONT)
    headers = ["Ativo", "1ª sexta", "Sexta atual", "Variação"]
    x = x0
    for text, wcol in zip(headers, cols):
        c.drawString(x + pad_x, y - row_h + 6, text)
        x += wcol

    # Linhas
    c.setFont(*ROW_FONT)
    y_cur = y - row_h
    for i, r in enumerate(rows):
        y_cur -= row_h
        if y_cur < 80:  # margem inferior
            break

        # zebra
        if i % 2 == 0:
            c.setFillColorRGB(0.05, 0.05, 0.05)
            c.rect(x0, y_cur, total_w, row_h, stroke=0, fill=1)
        else:
            c.setFillColorRGB(0.08, 0.08, 0.08)
            c.rect(x0, y_cur, total_w, row_h, stroke=0, fill=1)

        # textos
        name = (r.get("company_name") or r.get("symbol") or "").strip()
        sym  = (r.get("symbol") or "").strip().upper()
        p0   = r.get("p0")
        p1   = r.get("p1")
        chg  = r.get("chg")

        ativo_txt = f"{name} ({sym})"
        p0_txt = "—" if p0 is None else fmt_currency_usd(p0)
        p1_txt = "—" if p1 is None else fmt_currency_usd(p1)
        chg_txt = "—" if chg is None else f"{chg:+.2f}%"

        # colunas
        x = x0
        c.setFillColorRGB(1, 1, 1)
        # Ativo: usa wrap 1 linha para truncar elegante
        wrap_and_draw(c, ativo_txt, x + pad_x, y_cur + row_h - 6, cols[0] - 2*pad_x, 12, ROW_FONT, max_lines=1)
        x += cols[0]

        c.drawRightString(x + cols[1] - pad_x, y_cur + 6, p0_txt)
        x += cols[1]

        c.drawRightString(x + cols[2] - pad_x, y_cur + 6, p1_txt)
        x += cols[2]

        # variação com cor
        if chg is None:
            c.setFillColorRGB(1, 1, 1)
        elif chg >= 0:
            c.setFillColorRGB(0.12, 0.85, 0.40)
        else:
            c.setFillColorRGB(0.95, 0.35, 0.35)
        c.drawRightString(x + cols[3] - pad_x, y_cur + 6, chg_txt)

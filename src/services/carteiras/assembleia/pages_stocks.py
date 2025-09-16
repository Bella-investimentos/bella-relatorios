from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
import os

from .constants import (
    MINI_LBL, MINI_R, BIG_LBL, BIG_VAL, MINI_PAD, MINI_VAL,
    img_path, ETF_PAGE_BG_IMG,
)
from .utils import (
    draw_label_value_centered,
    fmt_currency_usd, wrap_and_draw, draw_centered_in_box, fmt_pct,draw_justified_paragraph,
    JUSTIFIED_WHITE,
)

STK_SPEC = {
    "bg": ETF_PAGE_BG_IMG,

    "logo":     {"x": 60,  "y": 700, "w": 60, "h": 60},
    "title":    {"x": 140, "y": 720, "w": 420, "lh": 30, "font": ("Helvetica-Bold", 26), "max_lines": 2},
    "subtitle": {"x": 140, "y": 665, "font": ("Helvetica-Bold", 16)},

    # gráfico
    "chart": {"x": 60, "y": 195, "w": 490, "h": 240, "border": False},

    # linhas y e alturas
    "row1_y": 580,      # Valor | VP | Score
    "row2_y": 530,      # VR | VS | Dividendos
    "row3_y": 450,      # EMA10 | EMA20 | Meta
    "h_small": 42,
    "h_large": 70,
    "gap_x": 12,

    # boxes (preenchidos pelo align)
    "card_price": {"x": 0, "y": 0, "w": 0, "h": 0},
    "card_vp":    {"x": 0, "y": 0, "w": 0, "h": 0},
    "card_score": {"x": 0, "y": 0, "w": 0, "h": 0},

    "vr_box":     {"x": 0, "y": 0, "w": 0, "h": 0},
    "vs_box":     {"x": 0, "y": 0, "w": 0, "h": 0},
    "card_div":   {"x": 0, "y": 0, "w": 0, "h": 0},

    "card_ema10": {"x": 0, "y": 0, "w": 0, "h": 0},
    "card_ema20": {"x": 0, "y": 0, "w": 0, "h": 0},
    "card_meta":  {"x": 0, "y": 0, "w": 0, "h": 0},

    # nota/descrição
    "note":  {"x": 60, "y": 50, "w": 490, "h": 90, "font": ("Helvetica", 11), "lh": 14, "max_lines": 10},
}

def _align_stock_cards(spec):
    g    = spec["chart"]
    gap  = spec.get("gap_x", 12)
    colw = (g["w"] - 2*gap) / 3.0

    x0 = g["x"]
    x1 = x0 + colw + gap
    x2 = x1 + colw + gap

    y1 = spec.get("row1_y", 580)
    y2 = spec.get("row2_y", 530)
    y3 = spec.get("row3_y", 450)
    hS = spec.get("h_small", 35)
    hL = spec.get("h_large", 70)

    # 1ª linha
    for k, x in (("card_price", x0), ("card_vp", x1), ("card_score", x2)):
        spec[k].update(x=int(x), y=y1, w=int(colw), h=hS)

    # 2ª linha
    for k, x in (("vr_box", x0), ("vs_box", x1), ("card_div", x2)):
        spec[k].update(x=int(x), y=y2, w=int(colw), h=hS)

    # 3ª linha (grandes)
    for k, x in (("card_ema10", x0), ("card_ema20", x1), ("card_meta", x2)):
        spec[k].update(x=int(x), y=y3, w=int(colw), h=hL)

def normalize_stock(s: dict) -> dict:
    return {
        "symbol": (s.get("symbol") or "").upper(),
        "company_name": s.get("company_name") or s.get("name") or s.get("longName") or "",
        "unit_price": s.get("unit_price") if "unit_price" in s else s.get("unitPrice"),
        "dividend_yield": s.get("dividend_yield") if "dividend_yield" in s else s.get("dividendYield"),
        "ema_10": s.get("ema_10") if "ema_10" in s else s.get("ema10"),
        "ema_20": s.get("ema_20") if "ema_20" in s else s.get("ema20"),
        "target_price": s.get("target_price") if "target_price" in s else s.get("targetPrice"),
        "score": s.get("score"),
        "vr": s.get("vr"),
        "vs": s.get("vs"),
        "vp": s.get("vp"),
        "chart": s.get("chart"),
        "logo_path": s.get("logo_path") or s.get("logoPath"),
        "sector": s.get("sector") or "",
        "asset_type": "STOCK",
        "asset_label": s.get("asset_label") or "Ação",
        "note": s.get("note") or "",
    }

def draw_stock_page(
    c: Canvas,
    asset: dict,
    *,
    normalizer=normalize_stock,
    kind_label: str | None = None,
    show_score: bool = True,
):
    # copia + alinhamento
    spec = {k: (v.copy() if isinstance(v, dict) else v) for k, v in STK_SPEC.items()}
    _align_stock_cards(spec)

    w, h = A4
    c.drawImage(img_path(spec["bg"]), 0, 0, width=w, height=h)

    s = normalizer(asset)
    
    # >>> RECENTRAR linha 1 para REITs (sem Score)
    if not show_score:
        g    = spec["chart"]
        gap  = spec.get("gap_x", 12)
        y1   = spec.get("row1_y", 580)
        hS   = spec.get("h_small", 35)

        # duas colunas (Valor, VP) com 1 gap entre elas
        colw2   = spec["card_price"]["w"]
        total_w = 2*colw2 + gap
        x_left  = g["x"] + (g["w"] - total_w) / 2.0

        # reposiciona os boxes
        spec["card_price"].update(x=int(x_left),                 y=y1, w=int(colw2), h=hS)
        spec["card_vp"].update(   x=int(x_left + colw2 + gap),   y=y1, w=int(colw2), h=hS)

        # “anula” o card_score (não será desenhado, mas evita interferência)
        spec["card_score"].update(x=0, y=0, w=0, h=0)

 
    # logo
    if s.get("logo_path"):
        try:
            c.drawImage(s["logo_path"], spec["logo"]["x"], spec["logo"]["y"],
                        width=spec["logo"]["w"], height=spec["logo"]["h"], mask='auto')
        except Exception as exc:
            print(f"[assembleia][STOCK] logo não carregada: {exc}")

    # título e subtítulo
    c.setFillColorRGB(1,1,1)
    wrap_and_draw(
        c,
        f'{s.get("company_name","")} ({s.get("symbol","")})',
        spec["title"]["x"], spec["title"]["y"],
        spec["title"]["w"], spec["title"]["lh"],
        spec["title"]["font"], spec["title"]["max_lines"]
    )
    c.setFillColorRGB(0.20, 0.49, 0.87)
    c.setFont(*spec["subtitle"]["font"])
    label = kind_label or s.get("asset_label") or "Ação"
    c.drawString(spec["subtitle"]["x"], spec["subtitle"]["y"], f"Tipo de Ativo: {label}")

    # helpers locais (usam 'c')
    CARD_PAD = {"t": 22, "r": 12, "b": 12, "l": 12}  # +4 no topo e +2 no bottom dá mais “respiro”
    LABEL_H  = 28                                    # reserva maior entre label e valor → valor desce


    def label_value_card(box, label_text, value_text):
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1)
        c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)
        draw_label_value_centered(
            c, box, label_text, value_text,
            label_font=MINI_LBL, value_font=MINI_VAL, pad_top=MINI_PAD["t"] + 20
        )

    def green_card(x, y, w, h, label_text, value):
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(0.10, 0.80, 0.35); c.setLineWidth(2)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
        c.setFillColorRGB(1,1,1); c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + w/2, y + h - CARD_PAD["t"], label_text)
        ix, iy = x + CARD_PAD["l"], y + CARD_PAD["b"]
        iw = w - CARD_PAD["l"] - CARD_PAD["r"]
        ih = h - CARD_PAD["t"] - LABEL_H - CARD_PAD["b"]
        c.setFillColorRGB(0.10,0.80,0.35); c.setFont("Helvetica-Bold", 22)
        draw_centered_in_box(c, value, ix, iy, iw, ih, ("Helvetica-Bold", 22))

    def blue_card(x, y, w, h, label_text, value):
        c.setFillColorRGB(0.06,0.06,0.06)
        c.setStrokeColorRGB(0.20,0.55,0.95); c.setLineWidth(2)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
        c.setFillColorRGB(1,1,1); c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + w/2, y + h - CARD_PAD["t"], label_text)
        ix, iy = x + CARD_PAD["l"], y + CARD_PAD["b"]
        iw = w - CARD_PAD["l"] - CARD_PAD["r"]
        ih = h - CARD_PAD["t"] - LABEL_H - CARD_PAD["b"]
        c.setFillColorRGB(0.75,0.85,1.0); c.setFont("Helvetica-Bold", 22)
        draw_centered_in_box(c, value, ix, iy, iw, ih, ("Helvetica-Bold", 22))

    # valores formatados
    price_str = fmt_currency_usd(s.get("unit_price")) if s.get("unit_price") is not None else " "
    vp_str    = fmt_pct(s.get("vp"))
    score_str = f"{float(s['score']):.1f}" if s.get("score") is not None else " "
    div_val = s.get("dividend_yield")
    if div_val is not None and 0 <= div_val <= 1:
        div_val *= 100.0
    div_str  = f"{div_val:.2f}%" if div_val is not None else " "

    vr_str = f"{s['vr']:.2f}"   if s.get("vr") is not None else " "
    vs_str = f"{s['vs']:+.2f}%" if s.get("vs") is not None else " "

    ema10_str = fmt_currency_usd(s["ema_10"])       if s.get("ema_10")       is not None else "–"
    ema20_str = fmt_currency_usd(s["ema_20"])       if s.get("ema_20")       is not None else "–"
    meta_str  = fmt_currency_usd(s["target_price"]) if s.get("target_price") is not None else "–"

    # 1ª linha
    label_value_card(spec["card_price"], "Valor",  price_str)
    label_value_card(spec["card_vp"],    "VP",     vp_str)
    if show_score:  # <- só desenha se permitido
        label_value_card(spec["card_score"], "Score", score_str)

    # 2ª linha
    label_value_card(spec["vr_box"],   "VR",         vr_str)
    label_value_card(spec["vs_box"],   "VS",         vs_str)
    label_value_card(spec["card_div"], "Dividendos", div_str)

    # 3ª linha (grandes)
    green_card(**spec["card_ema10"], label_text="Entrada (EMA 10)", value=ema10_str)
    green_card(**spec["card_ema20"], label_text="Entrada (EMA 20)", value=ema20_str)
    blue_card (**spec["card_meta"],  label_text="Meta (Saída)",     value=meta_str)

    # gráfico
    g = spec["chart"]
    if s.get("chart") and os.path.exists(s["chart"]):
        try:
            c.drawImage(s["chart"], g["x"], g["y"], width=g["w"], height=g["h"],
                        preserveAspectRatio=True, anchor='c')
        except Exception as exc:
            print(f"[assembleia][STOCK] gráfico não carregado: {exc}")
    if g.get("border"):
        c.setFillColorRGB(1,1,1); c.setLineWidth(1)
        c.roundRect(g["x"], g["y"], g["w"], g["h"], 6, stroke=1, fill=0)

    # nota
    n = spec["note"]
    c.setFillColorRGB(1,1,1)
    note_txt = s.get("note") or f"{s.get('company_name','')} ({s.get('symbol','')}) — visão geral/nota."
    draw_justified_paragraph(c, note_txt, n["x"], n["y"], n["w"], n["h"], JUSTIFIED_WHITE)



def normalize_reit(d: dict) -> dict:
    m = normalize_stock(d)
    m["asset_type"]  = "REIT"
    m["asset_label"] = "REIT"
    return m

def draw_reit_page(c: Canvas, reit: dict):
    return draw_stock_page(c, reit, normalizer=normalize_reit, kind_label="REIT", show_score=False)



def normalize_smallcap(d: dict) -> dict:
    m = normalize_stock(d)
    m["asset_type"]  = "SMALLCAP"
    m["asset_label"] = "Small Cap"
    return m

def draw_smallcap_page(c: Canvas, sc: dict):
    return draw_stock_page(c, sc, normalizer=normalize_smallcap, kind_label="Small Cap")

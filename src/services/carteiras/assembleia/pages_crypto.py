# src/services/carteiras/assembleia/pages_crypto.py
import os
from matplotlib.pyplot import box
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from .utils import JUSTIFIED_WHITE, draw_label_value_centered
from .constants import MINI_R, MINI_LBL, MINI_VAL, BIG_LBL, BIG_VAL, MINI_PAD
from .constants import img_path, ETF_PAGE_BG_IMG
from .utils import fmt_currency_usd, fmt_pct, wrap_and_draw, draw_centered_in_box, draw_justified_paragraph, JUSTIFIED_WHITE

# -----------------------------
# Normalização do payload
# -----------------------------
def normalize_crypto(d: dict) -> dict:
    return {
        "symbol":       (d.get("symbol") or "").upper(),                     # ex: BTC
        "company_name": d.get("company_name") or d.get("name") or "",        # ex: BITCOIN
        "unit_price":   d.get("unit_price") or d.get("price"),
        "vs":           d.get("vs") or d.get("variation") or d.get("weeklyChangePct"),
        "entry_price":  d.get("entry_price") or d.get("ema_20") or d.get("ema20"),
        "target_price": d.get("target_price") or d.get("targetPrice"),
        "chart":        d.get("chart"),
        "logo_path":    d.get("logo_path") or d.get("logoPath"),
        "note":         d.get("note") or "", 
    }

# -----------------------------
# Especificação de layout (SUAS COORDENADAS)
# -----------------------------
CRP_SPEC = {
    "bg": ETF_PAGE_BG_IMG,
    "logo":     {"x": 60,  "y": 700, "w": 60, "h": 60},
    "title":    {"x": 140, "y": 720, "w": 420, "lh": 30, "font": ("Helvetica-Bold", 26), "max_lines": 1},
    "subtitle": {"x": 140, "y": 680, "font": ("Helvetica-Bold", 15), "rgb": (0.15, 0.70, 0.55)},

    # mini-cards à esquerda (pretos) — manter nomes originais
    "card_price": {"x":  60, "y": 600, "w": 150, "h": 40},   # Valor
    "card_vs":    {"x":  60, "y": 550, "w": 150, "h": 40},   # VS

    # cards grandes à direita
    "card_entry": {"x": 235, "y": 550, "w": 150, "h": 90},   # verde
    "card_meta":  {"x": 400, "y": 550, "w": 150, "h": 90},   # azul

    # gráfico + nota
    "chart": {"x": 50, "y": 260, "w": 510, "h": 245, "border": True},
    "note":  {"x": 50, "y":  78, "w": 510, "h":  90, "font": ("Helvetica", 11), "lh": 14, "max_lines": 6},
}

# -----------------------------
# Desenho da página
# -----------------------------
def draw_crypto_page(c: Canvas, payload: dict):
    # cópia local do spec (evita mutar o global)
    spec = {k: (v.copy() if isinstance(v, dict) else v) for k, v in CRP_SPEC.items()}

    # fundo
    w, h = A4
    c.drawImage(img_path(spec["bg"]), 0, 0, width=w, height=h)

    d = normalize_crypto(payload)

    # logo
    if d.get("logo_path"):
        try:
            c.drawImage(d["logo_path"], spec["logo"]["x"], spec["logo"]["y"],
                        width=spec["logo"]["w"], height=spec["logo"]["h"], mask='auto')
        except Exception:
            pass

    # título
    c.setFillColorRGB(1, 1, 1)
    wrap_and_draw(
        c,
        f'{d.get("company_name","")} ({d.get("symbol","")})',
        spec["title"]["x"], spec["title"]["y"],
        spec["title"]["w"], spec["title"]["lh"],
        spec["title"]["font"], spec["title"]["max_lines"]
    )

    # subtítulo
    c.setFillColorRGB(*spec["subtitle"]["rgb"])
    c.setFont(*spec["subtitle"]["font"])
    c.drawString(spec["subtitle"]["x"], spec["subtitle"]["y"], "Tipo de Ativo: Criptomoeda")

    # estilos

    CARD_PAD = {"t": 55, "r": 12, "b": 12, "l": 12}   # sobe o topo reservado → valor desce
    LABEL_H  = 28
    MINI_PAD = {"t": 28, "r": 12, "b": 12, "l": 18}   # mini-cards (Valor / VS) descem também


    MINI_R    = 8                              # raio da borda dos mini-cards
    MINI_LBL  = ("Helvetica-Bold", 11)
    MINI_VAL  = ("Helvetica-Bold", 12)

    # ----- helpers de cards -----
    def small_black_card(box, label, value_text, pad_top=None):
        if pad_top is None:
            pad_top = MINI_PAD["t"]

        x, y, w, h = box["x"], box["y"], box["w"], box["h"]

        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1)
        c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)

        # Centraliza label/valor com fontes MINI
        draw_label_value_centered(
            c, box, label, value_text,
            label_font=MINI_LBL, value_font=MINI_VAL, pad_top=pad_top
        )


    def green_card(x, y, w, h, label, value):
        # container com borda verde
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(0.12, 0.75, 0.35); c.setLineWidth(2)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)

        # label branco e valor verde, ambos centralizados (fonte grande)
        draw_label_value_centered(
            c, {"x": x, "y": y, "w": w, "h": h},
            label, value,
            label_font=BIG_LBL, value_font=BIG_VAL,
            pad_top=CARD_PAD["t"],
            label_color=(1, 1, 1),
            value_color=(0.12, 0.85, 0.40),
        )


    def blue_card(x, y, w, h, label, value):
        # container com borda azul
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(0.25, 0.52, 0.95); c.setLineWidth(2)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)

        # label branco e valor azul claro, ambos centralizados (fonte grande)
        draw_label_value_centered(
            c, {"x": x, "y": y, "w": w, "h": h},
            label, value,
            label_font=BIG_LBL, value_font=BIG_VAL,
            pad_top=CARD_PAD["t"] ,
            label_color=(1, 1, 1),
            value_color=(0.75, 0.85, 1.0),
        )

    # ----- desenha os cards (sem mexer em coord.) -----
    small_black_card(spec["card_price"], "Valor", fmt_currency_usd(d.get("unit_price")))
    small_black_card(spec["card_vs"],    "VS",    fmt_pct(d.get("vs")))
    green_card(**spec["card_entry"], label="Entrada",     value=fmt_currency_usd(d.get("entry_price")))
    blue_card(**spec["card_meta"],  label="Meta (Saída)", value=fmt_currency_usd(d.get("target_price")))

    # ----- gráfico -----
    g = spec["chart"]
    if d.get("chart") and os.path.exists(d["chart"]):
        try:
            c.drawImage(d["chart"], g["x"], g["y"], width=g["w"], height=g["h"],
                        preserveAspectRatio=True, anchor='c')
        except Exception:
            pass
    if g.get("border"):
        c.setFillColorRGB(1, 1, 1); c.setLineWidth(1.2)
        c.roundRect(g["x"], g["y"], g["w"], g["h"], 8, stroke=1, fill=0)

    # ----- nota -----
    n = spec["note"]
    c.setFillColorRGB(1,1,1)
    note_txt = d.get("note") or f'{d.get("company_name","")} ({d.get("symbol","")}) — visão geral.'
    draw_justified_paragraph(c, note_txt, n["x"], n["y"], n["w"], n["h"], JUSTIFIED_WHITE)



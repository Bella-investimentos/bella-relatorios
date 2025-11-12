from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
import os
import copy
from .constants import MINI_R, MINI_LBL, MINI_VAL, MINI_PAD
from .utils import draw_label_value_centered
from .constants import BIG_LBL, BIG_VAL
from .constants import img_path, ETF_PAGE_BG_IMG
from .utils import fmt_currency_usd, wrap_and_draw, draw_centered_in_box, draw_justified_paragraph,draw_asset_logo_rounded, JUSTIFIED_WHITE



ETF_SPEC = {
    "bg": ETF_PAGE_BG_IMG,
    "logo":   {"x": 60,  "y": 665, "w": 75,  "h": 75},
    "title":  {"x": 140, "y": 720, "w": 420, "lh": 30, "font": ("Helvetica-Bold", 26), "max_lines": 2},
    "subtitle": {"x": 140, "y": 665, "font": ("Helvetica-Bold", 16)},

    # gráfico + nota (mantém sua largura base)
    "chart": {"x": 60, "y": 195, "w": 490, "h": 240, "border": False},
    "note":  {"x": 60, "y": 50,  "w": 490, "h": 90, "font": ("Helvetica", 11), "lh": 14, "max_lines": 10},

    # POSIÇÕES INICIAIS (serão realinhadas pelo código)
    "card_price": {"x": 60,  "y": 540, "w": 140, "h": 85},
    "card_div":   {"x": 230, "y": 540, "w": 140, "h": 85},
    "card_cagr":  {"x": 400, "y": 540, "w": 140, "h": 85},

    "vr_box":     {"x": 60,  "y": 490, "w": 140, "h": 40},   # metade da altura
    "vs_box":     {"x": 60,  "y": 445, "w": 140, "h": 40},   # metade da altura

    "card_ema10": {"x": 230, "y": 445, "w": 140, "h": 85},
    "card_ema20": {"x": 400, "y": 445, "w": 140, "h": 85},
    
}

def normalize_etf(e: dict) -> dict:
    return {
        "symbol": (e.get("symbol") or "").upper(),
        "company_name": e.get("company_name") or e.get("name") or e.get("longName") or "",
        "unit_price": e.get("unit_price") if "unit_price" in e else e.get("unitPrice"),
        "dividend_yield": e.get("dividend_yield") if "dividend_yield" in e else e.get("dividendYield"),
        "average_growth": e.get("average_growth") if "average_growth" in e else e.get("averageGrowth"),
        "ema_10": e.get("ema_10") if "ema_10" in e else e.get("ema10"),
        "ema_20": e.get("ema_20") if "ema_20" in e else e.get("ema20"),
        "chart": e.get("chart"),
        "vr": e.get("vr"),
        "vs": e.get("vs"),
        "vp": e.get("vp"),
        "logo_path": e.get("logo_path") or e.get("logoPath"),
        "sector": e.get("sector") or "",
        "asset_type": "ETF",
        "note": e.get("note") or "",
    }

def _align_cards_to_chart(spec: dict) -> dict:
    out = copy.deepcopy(spec)
    g = out["chart"]
    gap = 10
    col_w = (g["w"] - 2*gap) / 3.0
    x0 = g["x"]
    x1 = x0 + col_w + gap
    x2 = x1 + col_w + gap

    # use as posições originais para y/h (mantém seu layout)
    y1 = out["card_price"]["y"]; h1 = out["card_price"]["h"]
    y2 = out["vr_box"]["y"];     h2 = out["vr_box"]["h"]
    y3 = out["card_ema10"]["y"]; h3 = out["card_ema10"]["h"]

    # 1ª linha
    for key, x in (("card_price", x0), ("card_div", x1), ("card_cagr", x2)):
        out[key].update(x=int(x), y=y1, w=int(col_w), h=h1)

    # 2ª linha (VR/VS)
    out["vr_box"].update(x=int(x0), y=y2, w=int(col_w), h=h2)
    out["vs_box"].update(x=int(x0), y=out["vs_box"]["y"], w=int(col_w), h=out["vs_box"]["h"])

    # 3ª linha (EMA10/EMA20/META)
    out["card_ema10"].update(x=int(x1), y=y3, w=int(col_w), h=h3)
    out["card_ema20"].update(x=int(x2), y=y3, w=int(col_w), h=h3)

    return out


def draw_etf_page(c: Canvas, etf: dict, *, kind_label: str = "ETF"):
    # usa cópia alinhada para esta página
    spec = _align_cards_to_chart(ETF_SPEC)
    

    w, h = A4
    c.drawImage(img_path(spec["bg"]), 0, 0, width=w, height=h)

    e = normalize_etf(etf)

    # logo (opcional)
    try:
        drew = draw_asset_logo_rounded(
            c, e,
            spec["logo"]["x"], spec["logo"]["y"],
            spec["logo"]["w"], spec["logo"]["h"],
            radius=8,         # ajuste o raio que preferir
            draw_stroke=True,  # desenha uma bordinha
            stroke_width=1.0
        )
        #opcional: se quiser um placeholder quando não houver logo:
        if not drew:
            c.setFillColorRGB(0.9, 0.9, 0.9)
            c.rect(spec["logo"]["x"], spec["logo"]["y"], spec["logo"]["w"], spec["logo"]["h"], stroke=0, fill=1)
    except Exception as e:
        print(f"[bond] logo: {e}")

    # ----- TÍTULO / SUBTÍTULO
    c.setFillColorRGB(1, 1, 1)
    wrap_and_draw(
        c, f'({e.get("symbol","")}) {e.get("company_name","")}',
        spec["title"]["x"], spec["title"]["y"],
        spec["title"]["w"], spec["title"]["lh"],
        spec["title"]["font"], spec["title"]["max_lines"]
    )
    c.setFillColorRGB(0.20, 0.49, 0.87)
    c.setFont(*spec["subtitle"]["font"])
    c.drawString(spec["subtitle"]["x"], spec["subtitle"]["y"], f"Tipo de Ativo: {kind_label}")
    
    # =======================
    #   FUNÇÕES DE CARDS
    # =======================
    CARD_PAD = {"t": 55, "r": 12, "b": 12, "l": 12}   # era 22/18 → aumenta o topo
    LABEL_H  = 28
    MINI_PAD_LOCAL = {"t": 22, "r": 12, "b": 12, "l": 18}  # mini-cards VR/VS descem também

    def black_card(x, y, w, h, label, value):
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
        draw_label_value_centered(
            c, {"x": x, "y": y, "w": w, "h": h},
            label, value,
            label_font=BIG_LBL, value_font=BIG_VAL, pad_top=CARD_PAD["t"], 
        )

    def green_card(x, y, w, h, label, value):
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(0.10, 0.80, 0.35); c.setLineWidth(2)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
        draw_label_value_centered(
            c, {"x": x, "y": y, "w": w, "h": h},
            label, value,
            label_font=BIG_LBL, value_font=BIG_VAL, pad_top=CARD_PAD["t"],
            label_color=(1,1,1), value_color=(0.10,0.80,0.35)
        )

    def mini_card_box(box, label, value_text):
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        c.setFillColorRGB(0.06, 0.06, 0.06)
        c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1)
        c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)
        draw_label_value_centered(
            c, box, label, value_text,
            label_font=MINI_LBL, value_font=MINI_VAL, pad_top=MINI_PAD_LOCAL["t"] + 8,
        )

    # =======================
    #   VALORES FORMATADOS
    # =======================
    # 1ª linha
    div_val = e.get("dividend_yield")
    if div_val is not None and 0 <= div_val <= 1:
        div_val *= 100.0
    price_txt = "–" if e.get("unit_price") is None else fmt_currency_usd(e["unit_price"])
    div_txt   = "–" if div_val is None else f"{div_val:.2f}%"
    cagr      = e.get("average_growth")
    cagr_txt  = "–" if cagr is None else f"{cagr:.2f}%"

    # 2ª linha
    vr_txt = " " if e.get("vr") in (None, "") else f"{e['vr']}"
    if e.get("vs") is None:
        vs_txt = " "
    else:
        vs_txt = f"+{e['vs']:.2f}%" if e["vs"] >= 0 else f"{e['vs']:.2f}%"

    # 3ª linha
    ema10_val = e.get("ema_10")
    ema20_val = e.get("ema_20")
    ema10_txt = "–" if ema10_val is None else fmt_currency_usd(ema10_val)
    ema20_txt = "–" if ema20_val is None else fmt_currency_usd(ema20_val)

    # =======================
    #       RENDER
    # =======================
    # 1ª linha
    black_card(**spec["card_price"], label="Valor Atual", value=price_txt)
    black_card(**spec["card_div"],   label="Dividendos",  value=div_txt)
    black_card(**spec["card_cagr"],  label="Crescimento Médio a.a", value=cagr_txt)

    

    # 3ª linha
    green_card(**spec["card_ema10"], label="Entrada (EMA 10)", value=ema10_txt)
    green_card(**spec["card_ema20"], label="Entrada (EMA 20)", value=ema20_txt)

    # 2ª linha
    mini_card_box(spec["vr_box"], "VR:", vr_txt)
    mini_card_box(spec["vs_box"], "VS:", vs_txt)
    # ----- GRÁFICO
    g = spec["chart"]
    if e.get("chart") and os.path.exists(e["chart"]):
        try:
            c.drawImage(e["chart"], g["x"], g["y"], width=g["w"], height=g["h"],
                        preserveAspectRatio=True, anchor='c')
        except Exception as exc:
            print(f"[assembleia][ETF] gráfico não carregado: {exc}")
    if g.get("border"):
        c.setFillColorRGB(1, 1, 1); c.setLineWidth(1)
        c.roundRect(g["x"], g["y"], g["w"], g["h"], 6, stroke=1, fill=0)

    # ----- NOTA
    n = spec["note"]
    c.setFillColorRGB(1, 1, 1)
    note = e.get("note") or f"{e.get('company_name','')} ({e.get('symbol','')}) — resumo/nota opcional."
    draw_justified_paragraph(c, note, n["x"], n["y"], n["w"], n["h"], JUSTIFIED_WHITE)

def draw_hedge_page(c: Canvas, asset: dict):
    return draw_etf_page(c, asset, kind_label="Hedge")

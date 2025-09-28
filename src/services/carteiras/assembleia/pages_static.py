import os
import requests
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from .utils import translate_en_to_pt 

# IMPORTS que faltavam
from .constants import (
    CRYPTO, ETFS_MOD, ETFS_ARR, ETFS_CONS, SMALL_CAPS, STK_ARJ, STK_MOD, STK_OPP, img_path, CAPA_IMG, NEWS_BG_IMG,
    MODELO_PROTECAO, RISCO_CALCULADO, ACUMULO_CAPITAL, REITS, HEDGE, MENSAL, ETF_PAGE_BG_IMG # <- certifique-se de ter esses no constants.py
)
from .utils import wrap_and_draw  # <- usado para quebrar/desenhar texto


def onpage_capa(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(CAPA_IMG), 0, 0, width=w, height=h)


def fetch_general_market_news(api_key: str | None, limit: int = 3):
    """
    Busca notícias gerais do mercado americano via FMP.
    Usa os tickers-âncora SPY, QQQ, DIA, GLD para cobrir macro/índices.
    """
    if not api_key:
        return []
    base = "https://financialmodelingprep.com"
    try:
        url = f"{base}/api/v3/stock_news?tickers=SPY,QQQ,DIA,GLD&limit={limit}&apikey={api_key}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json() or []
        # saneamento: filtra itens sem title/url
        out = []
        for a in data:
            if a.get("title") and a.get("url"):
                out.append({
                    "title": a.get("title") or "",
                    "text": a.get("text") or "",
                    "url": a.get("url") or "",
                    "publishedDate": a.get("publishedDate") or "",
                })
        return out[:limit]
    except Exception as e:
        print(f"[NEWS] erro geral: {e}")
        return []

def draw_globe_icon(c: Canvas, cx: float, cy: float, size: float = 14):
    """
    Desenha um ícone simples de globo (círculo + meridianos/pares) centrado em (cx, cy).
    """
    r = size / 2.0
    c.saveState()
    c.setStrokeColorRGB(0.1, 0.12, 0.20)
    c.setLineWidth(1)
    # círculo
    c.circle(cx, cy, r, stroke=1, fill=0)
    # meridianos
    c.line(cx - r*0.9, cy, cx + r*0.9, cy)
    # pares “curvos” (aproximações com linhas)
    c.line(cx, cy - r*0.9, cx, cy + r*0.9)
    c.restoreState()


def onpage_noticias(c: Canvas, doc):
    # fundo
    w, h = A4
    c.drawImage(img_path(NEWS_BG_IMG), 0, 0, width=w, height=h)

    # áreas dos 3 cards
    cards = [
        (45, 335, 510, 121),  # topo
        (45, 200, 510, 121),  # meio
        (45,  70, 510, 121),  # baixo
    ]

    news = fetch_general_market_news(os.getenv("FMP_API_KEY"), limit=3)

    # estilos
    TITLE_FONT = ("Helvetica-Bold", 18)
    TITLE_LH   = 18
    TITLE_COLOR = (0.02, 0.28, 0.62)
    DESC_FONT  = ("Helvetica", 12)
    DESC_LH    = 14
    DESC_MAX   = 3
    DATE_FONT  = ("Helvetica-Oblique", 8)
    DATE_GRAY  = (0.35, 0.35, 0.35)

    LEFT_PAD   = 22
    RIGHT_ICON_GAP = 22
    TITLE_TOP  = 26  # dist. do topo do card até o baseline do título

    for i, (x, y, ww, hh) in enumerate(cards):
        art = news[i] if i < len(news) else None
        if not art:
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(x + LEFT_PAD, y + hh - 18, "Sem notícias disponíveis")
            continue
        
        title_en = (art.get("title") or "").strip()
        desc_en  = (art.get("text")  or "").strip()
        title_pt = translate_en_to_pt(title_en) or title_en
        desc_pt  = translate_en_to_pt(desc_en)  or desc_en
        url   = art.get("url") or ""
        date  = art.get("publishedDate") or ""

        # Título (máx 1 linha)
        c.setFillColorRGB(*TITLE_COLOR)
        wrap_and_draw(
            c, title_pt,
            x + LEFT_PAD, y + hh - TITLE_TOP,
            ww - LEFT_PAD - RIGHT_ICON_GAP,
            TITLE_LH, TITLE_FONT, 1,
            ellipsis=True
        )

        # Descrição (máx 2 linhas)
        c.setFillColorRGB(0, 0, 0)
        wrap_and_draw(
            c, desc_pt,
            x + LEFT_PAD, y + hh - (TITLE_TOP + 22),
            ww - LEFT_PAD - 12,
            DESC_LH, DESC_FONT, DESC_MAX,
            ellipsis=True
        )

        # Data (opcional)
        if date:
            c.setFillColorRGB(*DATE_GRAY)
            c.setFont(*DATE_FONT)
            c.drawRightString(x + ww - 8, y + 10, date)

        # Ícone do globo + links (sem usar 'cx')
        if url:
            # gx = x + ww - 14
            # gy = y + hh - TITLE_TOP + 2
            # draw_globe_icon(c, gx, gy, size=14)

            # Card inteiro clicável
            c.linkURL(url, (x, y, x + ww, y + hh))
            # Ícone clicável
            #c.linkURL(url, (gx - 10, gy - 10, gx + 10, gy + 10))

def onpage_perfil_cons(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(MODELO_PROTECAO), 0, 0, width=w, height=h)

def onpage_perfil_mod(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(RISCO_CALCULADO), 0, 0, width=w, height=h)

def onpage_perfil_arj(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(ACUMULO_CAPITAL), 0, 0, width=w, height=h)

def onpage_perfil_opp(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(STK_OPP), 0, 0, width=w, height=h)

def onpage_acao_mod(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(STK_MOD), 0, 0, width=w, height=h)

def onpage_acao_arr(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(STK_ARJ), 0, 0, width=w, height=h)

def onpage_acao_mod(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(STK_MOD), 0, 0, width=w, height=h)
    
def onpage_smallcap_arj(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(SMALL_CAPS), 0, 0, width=w, height=h)

def onpage_etfs_cons(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(ETFS_CONS), 0, 0, width=w, height=h)
    
def onpage_etfs_mod(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(ETFS_MOD), 0, 0, width=w, height=h)

def onpage_etfs_arr(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(ETFS_ARR), 0, 0, width=w, height=h)

def onpage_crypto(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(CRYPTO), 0, 0, width=w, height=h)
    
def onpage_reits(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(REITS), 0, 0, width=w, height=h)
    
def onpage_hedge(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(HEDGE), 0, 0, width=w, height=h)

def onpage_monthly(c: Canvas, doc):
    w, h = A4
    c.drawImage(img_path(MENSAL), 0, 0, width=w, height=h)

def onpage_text_asset(c, doc):
    w, h = A4
    c.drawImage(img_path(ETF_PAGE_BG_IMG), 0, 0, width=w, height=h)
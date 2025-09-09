import os
import requests
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

from .constants import img_path, NEWS_PAGE_BG_IMG, NEWS_SPEC
from .utils import (
    draw_image_cover,
    normalize_asset_minimal,
    wrap_and_draw,
    dedupe_sentences,
    translate_en_to_pt,   # ← IMPORTAR
)

# -------------------------------------------------
# Fetchers / Normalização
# -------------------------------------------------

def get_fmp_key() -> str:
    v = (os.getenv("FMP_API_KEY") or "").strip()     # remove espaços/linhas
    v = v.replace("\r", "").replace("\n", "")        # remove quebras
    # Se o .env estiver errado e a variável vier como "FMP_API_KEY=xxxx"
    if "FMP_API_KEY=" in v:
        v = v.split("=", 1)[1]
    return v

def _norm_news_item(d: dict) -> dict:
    """Normaliza item de notícia vindo de /general_news ou /stock_news."""
    return {
        "title": d.get("title") or d.get("headline") or "",
        "text": d.get("text") or d.get("content") or d.get("summary") or "",
        "url": d.get("url") or d.get("link") or "",
        "image": d.get("image") or d.get("image_url") or "",
        "publishedDate": d.get("publishedDate") or d.get("published_at") or d.get("date") or "",
    }

def fetch_asset_news(api_key: str, symbol: str, limit: int = 2):
    """Busca notícias para um ticker específico."""
    if not (api_key and symbol):
        return []
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={symbol.upper()}&limit={limit}&apikey={api_key}"
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json() or []
        return [_norm_news_item(x) for x in data[:limit]]
    except Exception as e:
        print(f"[NEWS] {symbol}: {e}")
        return []

def fetch_general_market_news(api_key: str | None, limit: int = 3):
    """
    Tenta em:
      1) /v3/general_news
      2) /v3/stock_news?tickers=SPY,QQQ,DIA,GLD
      3) /v3/stock_news (sem filtro)
    """
    if not api_key:
        print("[NEWS] FMP_API_KEY ausente.")
        return []

    base = "https://financialmodelingprep.com"
    endpoints = [
        f"{base}/api/v3/general_news?limit={limit}&apikey={api_key}",
        f"{base}/api/v3/stock_news?tickers=SPY,QQQ,DIA,GLD&limit={limit}&apikey={api_key}",
        f"{base}/api/v3/stock_news?limit={limit}&apikey={api_key}",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            data = r.json() or []
            if isinstance(data, list) and data:
                items = [_norm_news_item(x) for x in data[:limit]]
                print(f"[NEWS] {len(items)} itens obtidos de {url.split('/api/')[1]}")
                return items
        except Exception as e:
            print(f"[NEWS] falha em {url}: {e}")

    print("[NEWS] nenhuma notícia encontrada após fallbacks.")
    return []

# -------------------------------------------------
# Util local: quebra de linhas (para o título da tarja)
# -------------------------------------------------
def _wrap_lines_for_width(c, text, max_w, font, max_lines=3, ellipsis=True):
    name, size = font
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, name, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                cur = ""
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if ellipsis and len(lines) == max_lines:
        while lines and c.stringWidth(lines[-1] + " …", name, size) > max_w and len(lines[-1]) > 1:
            lines[-1] = lines[-1][:-1]
        if lines:
            lines[-1] += " …"
    return lines

# -------------------------------------------------
# Ícone de globo (pode ser usado em outras páginas)
# -------------------------------------------------
def draw_globe_icon(c: Canvas, cx: float, cy: float, size: float = 14):
    r = size / 2.0
    c.saveState()
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.10, 0.20, 0.55)
    # círculo
    c.circle(cx, cy, r, stroke=1, fill=0)
    # “meridiano” e “paralelo” centrais
    c.line(cx - r*0.9, cy, cx + r*0.9, cy)
    c.line(cx, cy - r*0.9, cx, cy + r*0.9)
    c.restoreState()

# -------------------------------------------------
# Render da página de 2 cards de notícia (por ativo)
# -------------------------------------------------
def draw_news_page(
    c: Canvas,
    asset: dict,
    spec: dict = NEWS_SPEC,
    bg_img: str | None = None,
    api_key: str | None = None
):
    """
    Desenha uma página com 2 cards de notícia para o ativo recebido.
    Cada card: imagem (cover), tarja preta com título (centralizado),
    e o rótulo “Acessar notícia” clicável abaixo do card.
    """
    # Fundo
    w, h = A4
    bg = bg_img or spec.get("bg") or NEWS_PAGE_BG_IMG
    c.drawImage(img_path(bg), 0, 0, width=w, height=h)

    # Busca notícias do símbolo
    a = normalize_asset_minimal(asset)
    api_key = api_key or get_fmp_key()
    arts = fetch_asset_news(api_key, a["symbol"], limit=2)

    def _draw_card(box, art: dict | None):
        x, y, W, H = box["x"], box["y"], box["w"], box["h"]
        r         = spec.get("radius", 8)
        strip_h   = spec.get("strip_h", 60)
        img_pad   = spec.get("img_pad", 4)

        # Fundo do card
        c.setFillColorRGB(*spec.get("ph_color", (0.95, 0.95, 0.95)))
        c.roundRect(x, y, W, H, r, stroke=0, fill=1)

        if not art:
            # placeholder sem conteúdo
            c.setFillColorRGB(0.40, 0.40, 0.40)
            c.setFont("Helvetica-Oblique", 10)
            c.drawCentredString(x + W/2, y + H/2, "Sem notícia disponível")
            return

        # Área da IMAGEM (cover), encostada na tarja
        img_x = x + img_pad
        img_y = y + strip_h
        img_w = W - 2 * img_pad
        img_h = H - strip_h

        img_url = art.get("image") or art.get("image_url") 
        if img_url:
            try:
                if img_url:
                    draw_image_cover(c, img_url, img_x, img_y, img_w, img_h)
            except Exception as exc:
                # fallback discreto
                c.setFillColorRGB(0.90, 0.90, 0.90)
                c.rect(img_x, img_y, img_w, img_h, stroke=0, fill=1)
                c.setFillColorRGB(0.4, 0.4, 0.4)
                c.setFont("Helvetica-Oblique", 9)
                c.drawCentredString(img_x + img_w/2, img_y + img_h/2, "Imagem indisponível")
        else:
            c.setFillColorRGB(0.90, 0.90, 0.90)
            c.rect(img_x, img_y, img_w, img_h, stroke=0, fill=1)

        # TARJA PRETA
        c.setFillColorRGB(0, 0, 0)
        c.roundRect(x, y, W, strip_h, r, stroke=0, fill=1)

        # TÍTULO na tarja (centralizado)
        title_en = (art.get("title") or "").strip()
        title_pt = translate_en_to_pt(title_en) or title_en
        title = dedupe_sentences(art.get("title") or "").strip() or "Sem título"
        pad   = spec.get("title_pad", 10)
        font  = spec.get("title_font", ("Helvetica-Bold", 11))
        lh    = spec.get("title_lh", 13)
        maxl  = spec.get("title_max_lines", 3)

        lines = _wrap_lines_for_width(c, title, W - 2*pad, font, max_lines=maxl, ellipsis=True)
        cx = x + W/2
        c.setFillColorRGB(1, 1, 1)
        c.setFont(*font)

        if not lines:
            lines = [""]

        first_baseline = y + strip_h/2 + ((len(lines) - 1) / 2.0) * lh
        for i, ln in enumerate(lines):
            c.drawCentredString(cx, first_baseline - i*lh, ln)

        # RÓTULO "Acessar notícia" (centralizado) + link
        # link_text = spec.get("link_text", "Acessar notícia")
        # c.setFont(*spec.get("link_font", ("Helvetica-Bold", 14)))
        # c.setFillColorRGB(*spec.get("link_color", (0.10, 0.12, 0.20)))
        # gap = spec.get("link_gap", 22)
        # label_y = box.get("label_y", y - gap)
        # c.drawCentredString(cx, label_y, link_text)

        # # sublinhado
        # tw = c.stringWidth(link_text, *spec.get("link_font", ("Helvetica-Bold", 14)))
        # c.setLineWidth(0.9)
        # c.line(cx - tw/2, label_y - 2, cx + tw/2, label_y - 2)

        # links clicáveis
        url = art.get("url")
        if url:
            # card todo
            c.linkURL(url, (x, y, x + W, y + H))
            # rótulo
            #c.linkURL(url, (cx - tw/2, label_y - 4, cx + tw/2, label_y + 12))

    # Desenha até 2 artigos
    cards = spec["cards"]
    _draw_card(cards[0], arts[0] if len(arts) > 0 else None)
    _draw_card(cards[1], arts[1] if len(arts) > 1 else None)

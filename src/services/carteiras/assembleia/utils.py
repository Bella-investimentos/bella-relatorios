from datetime import datetime
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib import colors
from io import BytesIO
import math 
import re
import os, requests

def fmt_currency_usd(v) -> str:
    """$1,234.56 | lida com None/NaN."""
    try:
        x = float(v)
        if not math.isfinite(x):
            return "–"
        return f"${x:,.2f}"
    except Exception:
        return "–"

def fmt_coupon(v) -> str:
    """7.0 -> 7.0% | 0.07 -> 7.0% | lida com None/NaN."""
    try:
        x = float(v)
        if not math.isfinite(x):
            return "–"
        pct = x * 100 if -1.5 <= x <= 1.5 else x
        return f"{pct:.1f}%"
    except Exception:
        return "–"

def fmt_pct(v) -> str:
    """Formata porcentagem. Se vier fracionário (|v|<=1.5), assume que é 0–1 e multiplica por 100."""
    if v is None:
        return "–"
    try:
        x = float(v)
        if not math.isfinite(x):
            return "–"
        if -1.5 <= x <= 1.5:
            x *= 100.0
        return f"{x:.2f}%"
    except Exception:
        return "–"

def fmt_date_ddmmyyyy(s: str) -> str:
    """Tenta normalizar para dd/mm/yyyy; se já vier assim, retorna o começo."""
    if not s:
        return "–"
    if "/" in s and len(s) >= 10:
        return s[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    return s

def wrap_and_draw(c: Canvas, text: str, x: float, y: float,
                  max_w: float, lh: float, font: tuple,
                  max_lines: int, align: str = "left", ellipsis: bool = True):
    """
    Quebra em linhas que caibam em max_w. y é a baseline da 1ª linha.
    Trata palavras gigantes (sem espaços) e adiciona reticências se estourar linhas.
    """
    txt = (text or "").strip()
    name, size = font
    c.setFont(name, size)

    words = txt.split()
    lines, cur = [], ""

    def fits(s: str) -> bool:
        return c.stringWidth(s, name, size) <= max_w

    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, name, size) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break

    if len(lines) < max_lines and cur:
        lines.append(cur)

    # aplica reticências na última linha se truncou
    if ellipsis and len(lines) == max_lines and (words and " ".join(lines) != txt):
        # garante que caiba " …"
        while lines and c.stringWidth(lines[-1] + " …", name, size) > max_w and len(lines[-1]) > 1:
            lines[-1] = lines[-1][:-1]
        if lines:
            lines[-1] += " …"

    yy = y
    for ln in lines:
        if align == "center":
            c.drawCentredString(x + max_w / 2, yy, ln)
        elif align == "right":
            c.drawRightString(x + max_w, yy, ln)
        else:
            c.drawString(x, yy, ln)
        yy -= lh

def draw_centered_in_box(c: Canvas, text: str, x: float, y: float, w: float, h: float, font: tuple):
    """
    Centraliza texto no retângulo (x,y,w,h). Baseline vertical aproximada (0.75*size).
    """
    name, size = font
    c.setFont(name, size)
    t = str(text or "")
    tw = c.stringWidth(t, name, size)
    tx = x + (w - tw) / 2
    ty = y + (h - size * 0.75) / 2 + size * 0.75  # centraliza pela “ascender” aproximada
    c.drawString(tx, ty, t)

def draw_image_cover(c, src, x, y, w, h, timeout=4):
    """
    Desenha uma imagem cobrindo a área (cover). Aceita caminho local ou URL.
    Usa timeout para URL e cai em placeholder se falhar.
    """
    try:
        if isinstance(src, str) and src.lower().startswith(("http://", "https://")):
            r = requests.get(src, timeout=timeout)
            r.raise_for_status()
            img = ImageReader(BytesIO(r.content))
        else:
            if not (isinstance(src, str) and os.path.exists(src)):
                raise FileNotFoundError("imagem não encontrada")
            img = ImageReader(src)

        iw, ih = img.getSize()
        scale = max(w/float(iw), h/float(ih))
        dw, dh = iw*scale, ih*scale
        dx = x + (w - dw)/2.0
        dy = y + (h - dh)/2.0

        c.saveState()
        p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0, fill=0)
        c.drawImage(img, dx, dy, width=dw, height=dh, mask='auto')
        c.restoreState()
    except Exception:
        # Placeholder discreto
        c.setFillColorRGB(0.90, 0.90, 0.90)
        c.rect(x, y, w, h, stroke=0, fill=1)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(x + w/2, y + h/2, "Imagem indisponível")

def normalize_asset_minimal(d: dict) -> dict:
    """Pega só o básico para páginas de notícia genéricas (símbolo + nome)."""
    return {
        "symbol": (d.get("symbol") or "").strip().upper(),
        "company_name": d.get("company_name") or d.get("name") or d.get("title") or (d.get("symbol") or ""),
    }

def squeeze_ws(text: str) -> str:
    """Normaliza espaços/quebras de linha em um único espaço."""
    return " ".join(str(text or "").split())

def dedupe_sentences(text: str, max_sentences: int | None = None) -> str:
    """
    Remove sentenças repetidas mantendo a ordem.
    Útil para resumos/descrições que vêm duplicados do feed.
    """
    t = squeeze_ws(text)
    if not t:
        return ""
    parts = re.split(r'(?<=[\.\!\?])\s+', t)  # divide em sentenças
    out, seen = [], set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if max_sentences and len(out) >= max_sentences:
            break
    return " ".join(out)

def translate_en_to_pt(text: str) -> str:
    if not text:
        return ""
    # 1) DeepL (se houver chave)
    deepl_key = os.getenv("DEEPL_API_KEY")
    if deepl_key:
        try:
            url = "https://api-free.deepl.com/v2/translate"
            headers = {"Authorization": f"DeepL-Auth-Key {deepl_key}"}
            data = {"text": text, "source_lang": "EN", "target_lang": "PT-BR"}
            r = requests.post(url, data=data, headers=headers, timeout=8)
            if r.ok:
                js = r.json()
                tr = (js.get("translations") or [{}])[0].get("text")
                if tr:
                    return tr
        except Exception as e:
            print(f"[TRAD] DeepL falhou: {e}")

    # 2) Google 'gtx' (sem chave; pode rate-limit)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "pt", "dt": "t", "q": text}
        r = requests.get(url, params=params, timeout=8)
        if r.ok:
            js = r.json()
            parts = []
            for chunk in js[0]:
                if chunk and len(chunk) > 0:
                    parts.append(chunk[0])
            tr = "".join(parts).strip()
            if tr:
                return tr
    except Exception as e:
        print(f"[TRAD] Google gtx falhou: {e}")

    # 3) LibreTranslate pública
    try:
        url = "https://libretranslate.de/translate"
        r = requests.post(url, json={"q": text, "source": "en", "target": "pt", "format": "text"}, timeout=8)
        if r.ok:
            tr = r.json().get("translatedText")
            if tr:
                return tr
    except Exception as e:
        print(f"[TRAD] LibreTranslate falhou: {e}")

    return text

JUSTIFIED_WHITE = ParagraphStyle(
    "justified_white",
    fontName="Helvetica",
    fontSize=12,
    leading=16,            # espaçamento entre linhas
    textColor=colors.white,
    alignment=TA_JUSTIFY,  # <<< justificado
)

def draw_justified_paragraph(c, text, x, y, w, h, style=JUSTIFIED_WHITE):
    """Desenha um parágrafo justificado ocupando a caixa (x,y,w,h),
    ancorando no topo da caixa."""
    if not text:
        return
    p = Paragraph(text.replace("\n", "<br/>"), style)
    pw, ph = p.wrap(w, h)              # calcula tamanho que cabe
    p.drawOn(c, x, y + h - ph)         # desenha colado no topo da caixa
    
# utils.py
# utils.py
def draw_label_value_centered(
    c,
    box: dict,
    label: str,
    value_text,
    label_font=None,
    value_font=None,
    pad_top: int | None = None,
    dash_if_empty: bool = True,
    label_color=(1, 1, 1),
    value_color=None,            # <- NOVO: cor do valor (se None, usa a do label)
):
    from .constants import MINI_LBL, MINI_VAL, MINI_PAD  # evita import circular

    label_font = label_font or MINI_LBL
    value_font = value_font or MINI_VAL
    pad_top = MINI_PAD["t"] if pad_top is None else pad_top

    x, y, w, h = box["x"], box["y"], box["w"], box["h"]

    # label centralizado no topo
    c.setFillColorRGB(*label_color)
    c.setFont(*label_font)
    c.drawCentredString(x + w / 2, y + h - pad_top, str(label))

    # valor central (horizontal e vertical)
    c.setFont(*value_font)
    if value_color is not None:
        c.setFillColorRGB(*value_color)
    txt = "" if value_text is None else str(value_text)
    if dash_if_empty and (txt.strip() == ""):
        txt = "–"

    val_h = value_font[1]
    vy = y + (h - val_h) / 2 + val_h * 0.85  # baseline ~centro visual
    c.drawCentredString(x + w / 2, vy, txt)

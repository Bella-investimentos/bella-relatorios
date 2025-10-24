# src/services/carteiras/assembleia/pages_monthly.py
from __future__ import annotations
from typing import Dict, Any, List,  Optional
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

from datetime import datetime, date

from .constants import img_path, ETF_PAGE_BG_IMG, BIG_LBL, BIG_VAL, MINI_R
from .utils import draw_label_value_centered, fmt_currency_usd

def _card(c: Canvas, x, y, w, h, label: str, value: str):
    c.setFillColorRGB(0.06,0.06,0.06)
    c.setStrokeColorRGB(1,1,1); c.setLineWidth(1)
    c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)
    
    # Ajuste nas fontes - diminuindo o tamanho dos valores
    label_font = ("Helvetica-Bold", 10)  # fonte menor para labels
    value_font = ("Helvetica-Bold", 16)  # fonte menor para valores (era BIG_VAL)
    
    draw_label_value_centered(
        c, {"x":x, "y":y, "w":w, "h":h},
        label, value,
        label_font=label_font, value_font=value_font, pad_top=40,  # menos padding
    )

# Versão adaptável do draw_monthly_cards_page que ajusta baseado na quantidade de itens

def draw_monthly_cards_page(c: Canvas, page: Dict[str, Any]):
    """
    Desenha página monthly com layout adaptável baseado na quantidade de itens
    """
    rows: List[Dict[str, Any]] = page.get("rows") or []
    label: str = page.get("label") or ""
    
    print(f"[DEBUG] draw_monthly_cards_page: {len(rows)} rows")

    w, h = A4
    
    # Fundo
    try:
        c.drawImage(img_path(ETF_PAGE_BG_IMG), 0, 0, width=w, height=h)
    except Exception:
        pass

    # Layout adaptável baseado na quantidade de rows
    num_rows = len(rows)
    
    if num_rows <= 10:
        # Layout padrão para até 10 itens
        top = h - 130
        row_h = 70
        gap_y = 25
        ch = 55
        max_rows = 10
        font_size_label = 10
        font_size_value = 14
    else:
        # Layout compacto mais de 9
        top = h - 130
        row_h = 70
        gap_y = 25
        ch = 55
        max_rows = 10
        font_size_label = 10
        font_size_value = 14
    

    # Posicionamento dos cards
    left = 50
    gutter = 10
    cw = 120
    
    x0 = left
    x1 = x0 + cw + gutter
    x2 = x1 + cw + gutter
    x3 = x2 + cw + gutter

    y = top
    count = 0
    
    # SUBSTITUA o loop principal por esta versão que usa a função _card original:

    for r in rows:
        if count >= max_rows:
            break
            
        sym = (r.get("symbol") or "")
        p0 = r.get("p0")
        p1 = r.get("p1")
        chg = r.get("chg")

        p0_txt = "—" if p0 is None else fmt_currency_usd(p0)
        p1_txt = "—" if p1 is None else fmt_currency_usd(p1)
        chg_txt = "—" if chg is None else f"{chg:+.2f}%"
    
        color = tuple(r.get("color") or (1,1,1))
        is_bond_placeholder = bool(r.get("placeholder_bond"))
        
        if is_bond_placeholder:
            # Cards vazios com borda azul - usando função personalizada
            blue = (0.20, 0.55, 0.95)
            _card_with_color(c, x0, y, cw, ch, "Ativo",   "", font_size_label, font_size_value, blue)
            _card_with_color(c, x1, y, cw, ch, "1ª semana", "", font_size_label, font_size_value, blue)
            _card_with_color(c, x2, y, cw, ch, "Valor Atual",    "", font_size_label, font_size_value, blue)
            _card_with_color(c, x3, y, cw, ch, "Var.%",    "", font_size_label, font_size_value, blue)
        else:
            # Cards normais com cores baseadas no grupo
            _card_with_color(c, x0, y, cw, ch, "Ativo",    sym,    font_size_label, font_size_value, color)
            _card_with_color(c, x1, y, cw, ch, "1ª Semana", p0_txt, font_size_label, font_size_value, color)
            _card_with_color(c, x2, y, cw, ch, "Valor Atual",    p1_txt, font_size_label, font_size_value, color)
            _card_with_color(c, x3, y, cw, ch, "Var.%",    chg_txt, font_size_label, font_size_value, color)

        y -= (row_h + gap_y)
        count += 1

# ADICIONE esta função nova no final do arquivo pages_monthly.py:

def _card_with_color(c: Canvas, x, y, w, h, label: str, value: str, label_font_size: int, value_font_size: int, color_rgb: tuple):
    """Card com cor personalizada para borda e texto"""
    c.setFillColorRGB(0.06, 0.06, 0.06)  # fundo escuro
    c.setStrokeColorRGB(*color_rgb)      # borda colorida
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)
    
    label_font = ("Helvetica-Bold", label_font_size)
    value_font = ("Helvetica-Bold", value_font_size)

    pad_top = 40 if h < 70 else 45  # padding adaptável

    draw_label_value_centered(
        c, {"x": x, "y": y, "w": w, "h": h},
        label, value,
        label_font=label_font, 
        value_font=value_font, 
        pad_top=pad_top,
        label_color=(1, 1, 1),    # label sempre branco
        value_color=color_rgb,    # valor com cor do grupo
    )
   

def _card_adaptive(c: Canvas, x, y, w, h, label: str, value: str, label_font_size: int, value_font_size: int, rgb=(1,1,1)):
    """Versão adaptável da função _card"""
    c.setFillColorRGB(0.06,0.06,0.06)
    c.setStrokeColorRGB(*rgb); c.setLineWidth(1)
    c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)
    
    label_font = ("Helvetica-Bold", label_font_size)
    value_font = ("Helvetica-Bold", value_font_size)
    
    pad_top = 40 if h < 70 else 45  # padding adaptável
    
    draw_label_value_centered(
        c, {"x":x, "y":y, "w":w, "h":h},
        label, value,
        label_font=label_font, value_font=value_font, pad_top=pad_top,
        label_color=rgb, value_color=rgb
    )
    
    
    #página com os cards que sairam do relatório


def _card_white(c: Canvas, x, y, w, h, label: str, value: str):
    """Card com borda e textos brancos (fundo dark do template)."""
    c.setFillColorRGB(0.06, 0.06, 0.06)   # fundo do card
    c.setStrokeColorRGB(1, 1, 1)          # borda branca
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, MINI_R, stroke=1, fill=1)

    label_font = ("Helvetica-Bold", 10)
    value_font = ("Helvetica-Bold", 16)

    draw_label_value_centered(
        c, {"x": x, "y": y, "w": w, "h": h},
        label, value,
        label_font=label_font,
        value_font=value_font,
        pad_top=40,
        label_color=(1, 1, 1),
        value_color=(1, 1, 1),
    )

# --- função principal da página ---

# --- NOVO: desenhar VÁRIOS itens de intervalo customizado em UMA ÚNICA PÁGINA ---
def draw_custom_range_page_many(
    c: Canvas,
    items: list[dict],
    *,
    fetch_price_fn,
    title: str = "Intervalos Personalizados",
):
    """
    Desenha MÚLTIPLAS páginas com até 10 linhas de cards brancos por página.
    Cada item do `items` deve conter: symbol, start_date, end_date.
    """
    from reportlab.lib.pagesizes import A4 as _A4
    w, h = _A4

    # util: parse de datas
    def _parse_date(s: str) -> date:
        s = (s or "").strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        raise ValueError(f"Data inválida: {s!r}. Use DD/MM/AAAA ou AAAA-MM-DD.")

    # geometria (mesma estética dos monthly)
    top    = h - 170
    row_h  = 70
    gap_y  = 25
    ch     = 55
    left   = 50
    gutter = 10
    cw     = 120
    
    ITEMS_PER_PAGE = 7  # limite de itens por página

    x0 = left
    x1 = x0 + cw + gutter
    x2 = x1 + cw + gutter
    x3 = x2 + cw + gutter

    # Processa e valida todos os itens primeiro
    valid_items = []
    for it in items:
        symbol = (it.get("symbol") or "").strip().upper()
        d0_str = it.get("start_date") or ""
        d1_str = it.get("end_date") or ""
        
        if not symbol or not d0_str or not d1_str:
            continue

        try:
            d0 = _parse_date(d0_str)
            d1 = _parse_date(d1_str)
            valid_items.append({
                "symbol": symbol,
                "d0": d0,
                "d1": d1,
                "d0_str": d0_str,
                "d1_str": d1_str
            })
        except Exception:
            continue

    # Divide os itens em páginas
    total_items = len(valid_items)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE  # arredonda pra cima
    
    for page_num in range(total_pages):
        # Desenha fundo
        try:
            c.drawImage(img_path(ETF_PAGE_BG_IMG), 0, 0, width=w, height=h)
        except Exception:
            pass

        # Título com número da página se houver mais de uma
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        if total_pages > 1:
            page_title = f"{title} - Página {page_num + 1}/{total_pages}"
        else:
            page_title = title
        c.drawCentredString(w/2, h - 70, page_title)

        # Pega os itens desta página
        start_idx = page_num * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        page_items = valid_items[start_idx:end_idx]

        y = top
        
        # Desenha os cards desta página
        for item_data in page_items:
            symbol = item_data["symbol"]
            d0 = item_data["d0"]
            d1 = item_data["d1"]

            p0 = fetch_price_fn(symbol, d0)
            p1 = fetch_price_fn(symbol, d1)
            chg = None
            if p0 not in (None, 0) and p1 not in (None, 0):
                chg = ((float(p1) / float(p0)) - 1.0) * 100.0

            p0_txt  = "—" if p0 is None else fmt_currency_usd(p0)
            p1_txt  = "—" if p1 is None else fmt_currency_usd(p1)
            chg_txt = "—" if chg is None else f"{chg:+.2f}%" 

            # Linha de 4 cards brancos
            _card_white(c, x0, y, cw, ch, "Ativo", symbol)
            _card_white(c, x1, y, cw, ch, f"Entrada {d0.strftime('%d/%m')}", p0_txt)
            _card_white(c, x2, y, cw, ch, f"Saída em {d1.strftime('%d/%m')}", p1_txt)
            _card_white(c, x3, y, cw, ch, "Var.%", chg_txt)

            y -= (row_h + gap_y)

        # Se não for a última página, cria nova página
        if page_num < total_pages - 1:
            c.showPage()
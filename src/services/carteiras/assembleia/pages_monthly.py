# src/services/carteiras/assembleia/pages_monthly.py
from typing import Dict, Any, List
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

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
        label_font=label_font, value_font=value_font, pad_top=15,  # menos padding
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

    # Título
    # c.setFillColorRGB(1,1,1)
    # c.setFont("Helvetica-Bold", 24)
    # title_y = h - 70
    # c.drawString(60, title_y, f"Resumo Mensal — {label}")

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
            _card_with_color(c, x1, y, cw, ch, "1ª Sexta", "", font_size_label, font_size_value, blue)
            _card_with_color(c, x2, y, cw, ch, "Atual",    "", font_size_label, font_size_value, blue)
            _card_with_color(c, x3, y, cw, ch, "Var.%",    "", font_size_label, font_size_value, blue)
        else:
            # Cards normais com cores baseadas no grupo
            _card_with_color(c, x0, y, cw, ch, "Ativo",    sym,    font_size_label, font_size_value, color)
            _card_with_color(c, x1, y, cw, ch, "1ª Sexta", p0_txt, font_size_label, font_size_value, color)
            _card_with_color(c, x2, y, cw, ch, "Atual",    p1_txt, font_size_label, font_size_value, color)
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
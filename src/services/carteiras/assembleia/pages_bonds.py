from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from .constants import img_path, BOND_PAGE_BG_IMG
from .utils import draw_justified_paragraph, fmt_currency_usd, fmt_coupon, fmt_date_ddmmyyyy, wrap_and_draw, draw_centered_in_box

BOND_SPEC = {
    "bg": BOND_PAGE_BG_IMG,
    "logo":   {"x": 68,  "y": 680, "w": 60,  "h": 60},
    "title":  {"x": 140, "y": 700, "w": 400, "lh": 24, "font": ("Helvetica-Bold", 30), "max_lines": 2},
    "type":   {"x": 260, "y": 645, "font": ("Helvetica", 14)},
    "sector": {"x": 405, "y": 645, "font": ("Helvetica", 14)},
    "card_venc": {"x":  50, "y": 520, "w": 180, "h": 70, "font": ("Helvetica-Bold", 20)},
    "card_cupom":{"x": 215, "y": 520, "w": 180, "h": 70, "font": ("Helvetica-Bold", 24)},
    "card_preco":{"x": 365, "y": 520, "w": 180, "h": 70, "font": ("Helvetica-Bold", 20)},
    "desc_box": {"x": 56, "y": 295, "w": 490, "h": 175, "pad": 16, "font": ("Helvetica", 12), "lh": 15, "max_lines": 11},
    "long_text": {"x": 56, "y": 140, "w": 490, "h": 90, "font": ("Helvetica", 12), "lh": 16, "max_lines": 10},
}

def normalize_bond(b: dict) -> dict:
    return {
        "name":        b.get("name") or b.get("title") or "",
        "code":        b.get("code") or b.get("isin") or "",
        "maturity":    b.get("maturity") or b.get("vencimento") or "",
        "unit_price":  b.get("unit_price") if "unit_price" in b else b.get("unitPrice"),
        "coupon":      b.get("coupon"),
        "sector":      b.get("sector") or "",
        "asset_type":  b.get("asset_type") or b.get("assetType") or "Bonds",
        "description": b.get("description") or [],
        "logo_path":   b.get("logo_path") or b.get("logoPath"),
        "summary":     b.get("summary") or b.get("resumo") or "",
        "prev_unit_price": (
            b.get("prev_unit_price")
            if "prev_unit_price" in b else
            b.get("previousUnitPrice") or b.get("previous_price") or b.get("prevPrice")
        ),
    }

def draw_bond_page(c: Canvas, bond: dict):
    w, h = A4
    spec = BOND_SPEC
    c.drawImage(img_path(spec["bg"]), 0, 0, width=w, height=h)

    b = normalize_bond(bond)

    # logo (opcional)
    if b["logo_path"]:
        try:
            c.drawImage(b["logo_path"], spec["logo"]["x"], spec["logo"]["y"],
                        width=spec["logo"]["w"], height=spec["logo"]["h"], mask='auto')
        except Exception as e:
            print(f"[bond] logo: {e}")

    # título
    c.setFillColorRGB(1, 1, 1)
    wrap_and_draw(
        c, b["name"],
        spec["title"]["x"], spec["title"]["y"],
        spec["title"]["w"], spec["title"]["lh"],
        spec["title"]["font"], spec["title"]["max_lines"]
    )

    # tipo & setor
    c.setFont(*spec["type"]["font"])
    c.drawString(spec["type"]["x"], spec["type"]["y"], b["asset_type"] or "Bonds")
    c.setFont(*spec["sector"]["font"])
    c.drawString(spec["sector"]["x"], spec["sector"]["y"], b["sector"] or "—")

    # cards
    c.setFillColorRGB(1, 1, 1)
    draw_centered_in_box(c, fmt_date_ddmmyyyy(b["maturity"]),
                         **{k: spec["card_venc"][k] for k in ("x","y","w","h")},
                         font=spec["card_venc"]["font"])
    draw_centered_in_box(c, fmt_coupon(b["coupon"]),
                         **{k: spec["card_cupom"][k] for k in ("x","y","w","h")},
                         font=spec["card_cupom"]["font"])
    draw_centered_in_box(c, fmt_currency_usd(b["unit_price"]),
                         **{k: spec["card_preco"][k] for k in ("x","y","w","h")},
                         font=spec["card_preco"]["font"])
    
    prev_txt = fmt_currency_usd(b.get("prev_unit_price")) if b.get("prev_unit_price") is not None else "--"
    px, py = spec["card_preco"]["x"], spec["card_preco"]["y"]
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 8)
    c.drawString(px + 50, py - 2, f"Preço anterior: {prev_txt}")
    
    # descrição (texto preto)
    box = spec["desc_box"]
    x_in = box["x"] + box["pad"]
    y_in = box["y"] + box["h"] - box["pad"]
    w_in = box["w"] - 2 * box["pad"]
    lh   = box["lh"]
    maxl = box["max_lines"]

    c.setFont(*box["font"])
    c.setFillColorRGB(0, 0, 0)

    lines = b["description"] if isinstance(b["description"], list) else [str(b["description"])]
    lines = [ln.strip() for ln in lines if str(ln).strip()]
    drawn = 0
    for ln in lines:
        if drawn >= maxl:
            break
        wrap_and_draw(c, ln, x_in, y_in - drawn * lh, w_in, lh, box["font"], 1, ellipsis=True)
        drawn += 1

    # resumo (texto branco, área long_text)
    if b["summary"]:
        s = spec["long_text"]
        c.setFillColorRGB(1, 1, 1)
        draw_justified_paragraph(
                c,
                b["summary"],
                s["x"], s["y"], s["w"], s["h"]
            )

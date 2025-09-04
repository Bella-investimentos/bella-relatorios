import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
# ajuste este caminho ao seu projeto
IMAGES_DIR = BASE_DIR.parent.parent.parent / "api" / "static" / "images"

CAPA_IMG         = "Capa.png"
NEWS_BG_IMG      = "Principais_noticias.png"
MODELO_PROTECAO  = "Perfil_conservador.png"
RISCO_CALCULADO  = "Perfil_moderado.png"
ACUMULO_CAPITAL  = "Perfil_arrojado.png"
BOND_PAGE_BG_IMG = "Bond_template.png"
ETF_PAGE_BG_IMG  = "Fundo_geral.png"
NEWS_PAGE_BG_IMG = "Noticias.png"
STK_OPP          = "Oportunidade.png"
STK_MOD          = "Acoes_moderadas.png"
STK_ARJ          = "Acoes_arrojadas.png"
CRYPTO           = "Cripto.png"
REITS            = "Reits_conservadores.png"
ETFS_MOD          = "Etfs_mod.png"
ETFS_CONS          = "Etfs_cons.png"
ETFS_ARR           = "Etfs_arr.png"
SMALL_CAPS        = "Small_caps.png"



def img_path(filename: str) -> str:
    p = IMAGES_DIR / filename
    if not p.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {p}")
    return str(p)

NEWS_SPEC = {
    "bg": NEWS_PAGE_BG_IMG,
    "cards": [
        {"x": 180, "y": 470, "w": 390, "h": 320},
        {"x":  56, "y": 100, "w": 390, "h": 320},
    ],
    "img_pad": 5,
    "strip_h": 50,
    "title_pad": 10,
    "title_font": ("Helvetica-Bold", 16),
    "title_lh": 16,
    "title_max_lines": 2,
    "link_font": ("Helvetica-Bold", 14),
    "link_color": (0.10, 0.12, 0.20),
    "link_text": "Acessar notícia",
    "ph_color": (0.95, 0.95, 0.95),
    "radius": 3,
}
# ====== CARD FONTS / PADDING UNIFICADOS ======
MINI_LBL = ("Helvetica", 12)          # rótulo de mini-card
MINI_VAL = ("Helvetica-Bold", 14)     # valor de mini-card
BIG_LBL  = ("Helvetica-Bold", 12)     # rótulo de card grande (EMA, Meta, etc.)
BIG_VAL  = ("Helvetica-Bold", 26)     # valor de card grande

MINI_R   = 16
MINI_PAD = {"t": 12, "r": 12, "b": 10, "l": 12}

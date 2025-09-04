import traceback
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, PageTemplate, Frame, Paragraph, PageBreak, NextPageTemplate
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas

# suas funções/páginas
from .pages_static import (
    onpage_acao_arr, onpage_capa, onpage_etfs_arr, onpage_etfs_cons, onpage_etfs_mod,
    onpage_noticias, onpage_perfil_cons, onpage_perfil_mod, onpage_perfil_arj, onpage_perfil_opp,
    onpage_acao_mod, onpage_reits, onpage_smallcap_arj, onpage_crypto
)
from .pages_bonds import draw_bond_page
from .pages_etfs import draw_etf_page
from .pages_stocks import draw_smallcap_page, draw_stock_page, draw_reit_page
from .pages_crypto import draw_crypto_page
from .pages_news import draw_news_page
from .constants import img_path, BOND_PAGE_BG_IMG, ETF_PAGE_BG_IMG, NEWS_PAGE_BG_IMG


def generate_assembleia_report(
    bonds: list | None = None,
    etfs_cons: list | None = None,   # ETFs Conservadoras
    etfs_mod:  list | None = None,   # ETFs Moderadas
    etfs_agr:  list | None = None,   # ETFs Agressivas
    stocks_mod: list | None = None,  # Ações Moderadas
    stocks_arj: list | None = None,  # Ações Arrojadas
    stocks_opp: list | None = None,  # Ações Oportunidades
    reits_cons=None,                 # só CONSERVADOR
    smallcaps_arj=None,              # só ARROJADO
    crypto: list | None = None,
) -> BytesIO | None:
    try:
        bonds      = bonds or []
        etfs_cons  = etfs_cons or []
        etfs_mod   = etfs_mod  or []
        etfs_agr   = etfs_agr  or []
        stocks_mod = stocks_mod or []
        stocks_arj = stocks_arj or []
        stocks_opp = stocks_opp or []
        reits_cons     = reits_cons or []
        smallcaps_arj  = smallcaps_arj or []
        crypto = crypto or []

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        styles = getSampleStyleSheet()
        blank = Paragraph("", styles["Normal"])

        # Frame “dummy”
        frame = Frame(50, 50, A4[0]-100, A4[1]-100, id="f")

        # -------------------------
        # Fábricas genéricas
        # -------------------------
        def paged_onpage_factory(draw_fn, items: list, bg_img: str | None = None):
            state = {"i": 0}
            def _onpage(c: Canvas, doc):
                if state["i"] < len(items):
                    draw_fn(c, items[state["i"]])
                    state["i"] += 1
                else:
                    if bg_img:
                        try:
                            c.drawImage(img_path(bg_img), 0, 0, width=A4[0], height=A4[1])
                        except Exception:
                            pass
            return _onpage

        def news_onpage_factory(items: list):
            state = {"i": 0}
            def _onpage(c: Canvas, doc):
                if state["i"] < len(items):
                    draw_news_page(c, items[state["i"]])
                    state["i"] += 1
                else:
                    try:
                        c.drawImage(img_path(NEWS_PAGE_BG_IMG), 0, 0, width=A4[0], height=A4[1])
                    except Exception:
                        pass
            return _onpage

        # -------------------------
        # Templates fixos
        # -------------------------
        cover_t  = PageTemplate(id="Capa",     frames=[frame], onPage=onpage_capa)
        news_t   = PageTemplate(id="Noticias", frames=[frame], onPage=onpage_noticias)
        perfilcons_t = PageTemplate(id="PerfilConservador", frames=[frame], onPage=onpage_perfil_cons)
        perfilmod_t = PageTemplate(id="PerfilModerado", frames=[frame], onPage=onpage_perfil_mod)
        perfilarj_t = PageTemplate(id="PerfilArrojado", frames=[frame], onPage=onpage_perfil_arj)
        perfilopp_t = PageTemplate(id="Oportunidade", frames=[frame], onPage=onpage_perfil_opp)
        acao_mod_t = PageTemplate(id="Acoes_moderadas", frames=[frame], onPage=onpage_acao_mod)
        acao_arr_t = PageTemplate(id="Acoes_arrojadas", frames=[frame], onPage=onpage_acao_arr)
        crypto_t = PageTemplate(id="Crypto", frames=[frame], onPage=onpage_crypto)
        small_caps_t = PageTemplate(id="Small_caps", frames=[frame], onPage=onpage_smallcap_arj)
        etfs_mod_t = PageTemplate(id="Etfs_mod", frames=[frame], onPage=onpage_etfs_mod)
        etfs_cons_t = PageTemplate(id="Etfs_cons", frames=[frame], onPage=onpage_etfs_cons)
        etfs_arr_t = PageTemplate(id="Etfs_arr", frames=[frame], onPage=onpage_etfs_arr)
        reits_t = PageTemplate(id="Reits_conservadores", frames=[frame], onPage=onpage_reits)

        # ETFs
        etf_cons_t      = PageTemplate(id="ETF_CONS",      frames=[frame], onPage=paged_onpage_factory(draw_etf_page, etfs_cons, ETF_PAGE_BG_IMG))
        etf_cons_news_t = PageTemplate(id="ETF_CONS_NEWS", frames=[frame], onPage=news_onpage_factory(etfs_cons))

        etf_mod_t       = PageTemplate(id="ETF_MOD",       frames=[frame], onPage=paged_onpage_factory(draw_etf_page, etfs_mod,  ETF_PAGE_BG_IMG))
        etf_mod_news_t  = PageTemplate(id="ETF_MOD_NEWS",  frames=[frame], onPage=news_onpage_factory(etfs_mod))

        etf_agr_t       = PageTemplate(id="ETF_AGR",       frames=[frame], onPage=paged_onpage_factory(draw_etf_page, etfs_agr,  ETF_PAGE_BG_IMG))
        etf_agr_news_t  = PageTemplate(id="ETF_AGR_NEWS",  frames=[frame], onPage=news_onpage_factory(etfs_agr))

        # AÇÕES
        stk_mod_t       = PageTemplate(id="STK_MOD",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_mod, ETF_PAGE_BG_IMG))
        stk_mod_news_t  = PageTemplate(id="STK_MOD_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_mod))

        stk_arj_t       = PageTemplate(id="STK_ARJ",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_arj, ETF_PAGE_BG_IMG))
        stk_arj_news_t  = PageTemplate(id="STK_ARJ_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_arj))

        stk_opp_t       = PageTemplate(id="STK_OPP",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_opp, ETF_PAGE_BG_IMG))
        stk_opp_news_t  = PageTemplate(id="STK_OPP_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_opp))

        # REITs
        reit_cons_t      = PageTemplate(id="REIT_CONS",      frames=[frame], onPage=paged_onpage_factory(draw_reit_page, reits_cons, ETF_PAGE_BG_IMG))
        reit_cons_news_t = PageTemplate(id="REIT_CONS_NEWS", frames=[frame], onPage=news_onpage_factory(reits_cons))

        # Small Caps
        smcap_arj_t      = PageTemplate(id="SMCAP_ARJ",      frames=[frame], onPage=paged_onpage_factory(draw_smallcap_page, smallcaps_arj, ETF_PAGE_BG_IMG))
        smcap_arj_news_t = PageTemplate(id="SMCAP_ARJ_NEWS", frames=[frame], onPage=news_onpage_factory(smallcaps_arj))

        # Crypto
        crp_t = PageTemplate(id="CRP", frames=[frame], onPage=paged_onpage_factory(draw_crypto_page, crypto, ETF_PAGE_BG_IMG))
        crp_news_t = PageTemplate(id="CRP_NEWS", frames=[frame], onPage=news_onpage_factory(crypto))

        doc.addPageTemplates([
            cover_t, news_t, perfilcons_t, perfilmod_t, perfilarj_t, perfilopp_t,
            etf_cons_t, etf_cons_news_t,
            etf_mod_t,  etf_mod_news_t,
            etf_agr_t,  etf_agr_news_t,
            stk_mod_t,  stk_mod_news_t,
            stk_arj_t,  stk_arj_news_t,
            stk_opp_t,  stk_opp_news_t,
            acao_mod_t, acao_arr_t, 
            reit_cons_t, reit_cons_news_t,
            smcap_arj_t, smcap_arj_news_t, reits_t,
            crypto_t, crp_t, crp_news_t,
            small_caps_t,
            etfs_mod_t, etfs_cons_t, etfs_arr_t,
        ])

        # -------------------------
        # Helpers de Story
        # -------------------------
        def add_bonds(story, items):
            if not items:
                return
            for i, b in enumerate(items):
                tid = f"BOND_{i}"
                def make_onpage(bond=b):
                    def _onpage(c: Canvas, doc):
                        draw_bond_page(c, bond)
                    return _onpage
                doc.addPageTemplates([PageTemplate(id=tid, frames=[frame], onPage=make_onpage())])
                story.append(NextPageTemplate(tid))
                story.append(PageBreak())
                story.append(blank)

        def add_asset_section(story, tpl_id: str, news_tpl_id: str, items: list):
            if not items:
                return
            story.append(NextPageTemplate(tpl_id))
            for _ in items:
                story.append(PageBreak()); story.append(blank)
                story.append(NextPageTemplate(news_tpl_id))
                story.append(PageBreak()); story.append(blank)
                story.append(NextPageTemplate(tpl_id))

        # -------------------------
        # Story
        # -------------------------
        Story = []
        Story.append(blank); Story.append(NextPageTemplate("Noticias")); Story.append(PageBreak())
        Story.append(blank); Story.append(NextPageTemplate("PerfilConservador")); Story.append(PageBreak())
        Story.append(blank)

        add_bonds(Story, bonds) 

        Story.append(blank); Story.append(NextPageTemplate("Reits_conservadores")); Story.append(PageBreak())
        add_asset_section(Story, "REIT_CONS", "REIT_CONS_NEWS", reits_cons)
        Story.append(blank); Story.append(NextPageTemplate("Etfs_cons")); Story.append(PageBreak())
        add_asset_section(Story, "ETF_CONS", "ETF_CONS_NEWS", etfs_cons)

        Story.append(blank); Story.append(NextPageTemplate("PerfilModerado")); Story.append(PageBreak())
        Story.append(blank); Story.append(NextPageTemplate("Etfs_mod")); Story.append(PageBreak())
        add_asset_section(Story, "ETF_MOD",  "ETF_MOD_NEWS",  etfs_mod)
        Story.append(blank); Story.append(NextPageTemplate("Acoes_moderadas")); Story.append(PageBreak())
        add_asset_section(Story, "STK_MOD",  "STK_MOD_NEWS",  stocks_mod)

        Story.append(blank); Story.append(NextPageTemplate("PerfilArrojado")); Story.append(PageBreak())
        Story.append(blank); Story.append(NextPageTemplate("Etfs_arr")); Story.append(PageBreak())
        add_asset_section(Story, "ETF_AGR",  "ETF_AGR_NEWS",  etfs_agr)
        Story.append(blank); Story.append(NextPageTemplate("Acoes_arrojadas")); Story.append(PageBreak())
        add_asset_section(Story, "STK_ARJ",  "STK_ARJ_NEWS",  stocks_arj)

        if stocks_opp:
            Story.append(blank); Story.append(NextPageTemplate("Oportunidade")); Story.append(PageBreak())
            add_asset_section(Story, "STK_OPP",  "STK_OPP_NEWS",  stocks_opp)

        Story.append(blank); Story.append(NextPageTemplate("Small_caps")); Story.append(PageBreak())
        add_asset_section(Story, "SMCAP_ARJ",     "SMCAP_ARJ_NEWS",     smallcaps_arj)
        
        if crypto: 
            Story.append(blank); Story.append(NextPageTemplate("Crypto")); Story.append(PageBreak())
            add_asset_section(Story, "CRP", "CRP_NEWS", crypto)

        doc.build(Story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print("⚠️ Erro ao gerar relatório de assembleia:", e)
        traceback.print_exc()
        return None

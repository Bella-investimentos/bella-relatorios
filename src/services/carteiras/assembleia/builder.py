# src/services/carteiras/assembleia/builder.py
from io import BytesIO
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate, PageTemplate, Frame,
    Paragraph, PageBreak, NextPageTemplate
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import white, black

# Páginas estáticas (capas, perfis, índices, etc.)
from .pages_static import (
    onpage_capa, onpage_noticias,
    onpage_perfil_cons, onpage_perfil_mod, onpage_perfil_arj, onpage_perfil_opp,
    onpage_etfs_cons, onpage_etfs_mod, onpage_etfs_arr,
    onpage_acao_mod, onpage_acao_arr,
    onpage_reits, onpage_smallcap_arj,
    onpage_crypto, onpage_hedge, onpage_monthly, onpage_text_asset 
)

# Páginas “dinâmicas” (desenham conteúdo a partir de dados)
from .pages_bonds import draw_bond_page
from .pages_etfs import draw_etf_page, draw_hedge_page
from .pages_stocks import draw_stock_page, draw_reit_page, draw_smallcap_page
from .pages_crypto import draw_crypto_page
from .pages_news import draw_news_page
from .pages_monthly import draw_monthly_cards_page
from .pages_text_asset import draw_text_asset_page
from .constants import img_path, ETF_PAGE_BG_IMG, NEWS_PAGE_BG_IMG

from datetime import datetime
try:
    from zoneinfo import ZoneInfo      # Python 3.9+
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    import pytz                        # fallback se zoneinfo/tzdata não estiver disponível
    TZ = pytz.timezone("America/Sao_Paulo")


def generate_assembleia_report(
    bonds: list | None = None,
    etfs_cons: list | None = None,   # ETFs Conservadoras
    etfs_mod:  list | None = None,   # ETFs Moderadas
    etfs_agr:  list | None = None,   # ETFs Agressivas
    hedge: list | None = None,       # Hedge
    stocks_mod: list | None = None,  # Ações Moderadas
    stocks_arj: list | None = None,  # Ações Arrojadas
    stocks_opp: list | None = None,  # Ações Oportunidades
    reits_cons: list | None = None,  # REITs (conservador)
    smallcaps_arj: list | None = None,
    crypto: list | None = None,
    monthly_rows: list | None = None,
    monthly_label: str | None = None,
    custom_range_pages: list | None = None,   
    text_assets: list | None = None,
    fetch_price_fn=None,   
) -> BytesIO:

    # ---------- Normalização de entradas ----------
    bonds          = bonds or []
    etfs_cons      = etfs_cons or []
    etfs_mod       = etfs_mod or []
    etfs_agr       = etfs_agr or []
    hedge          = hedge or []
    stocks_mod     = stocks_mod or []
    stocks_arj     = stocks_arj or []
    stocks_opp     = stocks_opp or []
    reits_cons     = reits_cons or []
    smallcaps_arj  = smallcaps_arj or []
    crypto         = crypto or []
    monthly_rows   = monthly_rows or []
    monthly_label  = (monthly_label or "").strip()
    custom_range_pages = custom_range_pages or []
    text_assets = text_assets or []

    # ---------- Doc/Frame básicos ----------
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    styles = getSampleStyleSheet()
    blank = Paragraph("", styles["Normal"])

    # Frame “dummy” só para satisfazer o PageTemplate (desenhamos direto no onPage)
    frame = Frame(50, 50, A4[0] - 100, A4[1] - 100, id="f")

    # ---------- Helpers/Fábricas (definidos ANTES do uso) ----------
    def paged_onpage_factory(draw_fn, items: list, bg_img: str | None = None):
        """
        Para cada página, desenha o próximo item da lista com draw_fn(canvas, item).
        Quando os itens acabam, opcionalmente desenha apenas um BG (se passado).
        """
        state = {"i": 0}

        def _onpage(c: Canvas, _doc):
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
        """
        Usa o símbolo/nome do item corrente para montar a página de notícias.
        """
        state = {"i": 0}

        def _onpage(c: Canvas, _doc):
            if state["i"] < len(items):
                draw_news_page(c, items[state["i"]])
                state["i"] += 1
            else:
                try:
                    c.drawImage(img_path(NEWS_PAGE_BG_IMG), 0, 0, width=A4[0], height=A4[1])
                except Exception:
                    pass

        return _onpage

    def onpage_capa_with_date(c: Canvas, doc_):
        onpage_capa(c, doc_)
        data_str = datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")  # <- agora com fuso
        c.setFont("Helvetica", 9)
        c.setFillColor(white)
        c.drawRightString(A4[0] - 50, 20, f"{data_str}")
        c.setFillColor(black)

        
    # Substitua TODA a seção monthly no builder.py (desde paginate_monthly até o final da seção)

    def paginate_monthly(rows, per_page=8, label: str = ""):
        """
        Pagina os dados monthly de forma flexível
        
        Args:
            rows: Lista de dados dos ativos
            per_page: Número de itens por página (padrão 6)
            label: Label para todas as páginas
        
        Returns:
            Lista de páginas, cada uma com estrutura {"label": str, "rows": list}
        """
        print(f"[DEBUG] paginate_monthly: recebeu {len(rows)} rows, per_page={per_page}, label='{label}'")
        
        if not rows:
            print("[DEBUG] Sem rows, criando página vazia")
            return [{"label": label, "rows": []}]
        
        pages = []
        total_rows = len(rows)
        
        for i in range(0, total_rows, per_page):
            chunk = rows[i:i + per_page]
            page_num = (i // per_page) + 1
            total_pages = (total_rows + per_page - 1) // per_page  # ceil division
            
            pages.append({
                "label": label,
                "rows": chunk,
                "page_info": f"{page_num}/{total_pages}"  # info extra para debug
            })
            
            print(f"[DEBUG] Página {page_num}/{total_pages} criada com {len(chunk)} rows")
        
        print(f"[DEBUG] Total de {len(pages)} páginas criadas")
        return pages

    _monthly_pages = paginate_monthly(monthly_rows, per_page=8, label=monthly_label)

    # Criar templates individuais para cada página monthly
    monthly_templates = []
    monthly_static_t = PageTemplate(id="MONTHLY_STATIC", frames=[frame], onPage=onpage_monthly)

    # Criar um template para cada página de dados
    for i, page_data in enumerate(_monthly_pages):
        template_id = f"MONTHLY_DYN_{i}"
        
        def make_monthly_onpage(page=page_data, page_num=i):
            def _onpage(c: Canvas, _doc):
                print(f"[DEBUG] Template {template_id} - Desenhando página {page_num} com {len(page.get('rows', []))} rows")
                draw_monthly_cards_page(c, page)
            return _onpage
        
        template = PageTemplate(id=template_id, frames=[frame], onPage=make_monthly_onpage())
        monthly_templates.append(template)
        print(f"[DEBUG] Criado template {template_id} para página {i}")
        
    def custom_range_onpage_factory(items: list, fetch_price_fn):
        """Factory que cria função onPage para desenhar custom ranges"""
        def _onpage(c: Canvas, _doc):
            if items:  # se há itens, desenha todos numa página só
                from .pages_monthly import draw_custom_range_page_many
                draw_custom_range_page_many(
                    c, 
                    items, 
                    fetch_price_fn=fetch_price_fn,
                    title="ATIVOS INDICADOS QUE SAIRAM DO RELATÓRIO"
                )
            else:
                # só fundo
                try:
                    c.drawImage(img_path(ETF_PAGE_BG_IMG), 0, 0, width=A4[0], height=A4[1])
                except Exception:
                    pass
        return _onpage
    
    custom_range_templates = []
    if custom_range_pages:
        custom_range_t = PageTemplate(
            id="CUSTOM_RANGE", 
            frames=[frame], 
            onPage=custom_range_onpage_factory(custom_range_pages, fetch_price_fn)
        )
        custom_range_templates.append(custom_range_t)
        
    def paged_onpage_factory_simple(draw_fn, items: list, onpage_bg=None):
        """
        Desenha 1 item de `items` por página:
        1) pinta o fundo via onpage_bg(c, doc) se fornecido
        2) chama draw_fn(c, items[i]) e incrementa i
        """
        state = {"i": 0}

        def _onpage(c: Canvas, doc_):
            # 1) fundo
            if onpage_bg:
                onpage_bg(c, doc_)
            # 2) conteúdo
            if state["i"] < len(items):
                try:
                    draw_fn(c, items[state["i"]])
                except Exception as e:
                    print(f"[TEXT_ASSET] erro no item {state['i']}: {e}")
                finally:
                    state["i"] += 1
            # se passar do fim: só mantém o fundo (sem erro)

        return _onpage

        
    # ---------- Templates FIXOS (capas/perfis/headers) ----------
    cover_t      = PageTemplate(id="Capa",                frames=[frame], onPage=onpage_capa_with_date)
    news_t       = PageTemplate(id="Noticias",            frames=[frame], onPage=onpage_noticias)
    perfilcons_t = PageTemplate(id="PerfilConservador",   frames=[frame], onPage=onpage_perfil_cons)
    perfilmod_t  = PageTemplate(id="PerfilModerado",      frames=[frame], onPage=onpage_perfil_mod)
    perfilarj_t  = PageTemplate(id="PerfilArrojado",      frames=[frame], onPage=onpage_perfil_arj)
    perfilopp_t  = PageTemplate(id="Oportunidade",        frames=[frame], onPage=onpage_perfil_opp)
    acao_mod_t   = PageTemplate(id="Acoes_moderadas",     frames=[frame], onPage=onpage_acao_mod)
    acao_arr_t   = PageTemplate(id="Acoes_arrojadas",     frames=[frame], onPage=onpage_acao_arr)
    reits_hdr_t  = PageTemplate(id="Reits_conservadores", frames=[frame], onPage=onpage_reits)
    small_hdr_t  = PageTemplate(id="Small_caps",          frames=[frame], onPage=onpage_smallcap_arj)
    crypto_hdr_t = PageTemplate(id="Crypto",              frames=[frame], onPage=onpage_crypto)
    etfs_mod_hdr = PageTemplate(id="Etfs_mod",            frames=[frame], onPage=onpage_etfs_mod)
    etfs_cons_hdr= PageTemplate(id="Etfs_cons",           frames=[frame], onPage=onpage_etfs_cons)
    etfs_arr_hdr = PageTemplate(id="Etfs_arr",            frames=[frame], onPage=onpage_etfs_arr)
    hedge_hdr_t  = PageTemplate(id="HEDGE_HDR",           frames=[frame], onPage=onpage_hedge)
    monthly_static_t = PageTemplate(id="MONTHLY_STATIC",  frames=[frame], onPage=onpage_monthly)

    # ---------- Templates DINÂMICOS (um item por página) ----------
    etf_cons_t      = PageTemplate(id="ETF_CONS",      frames=[frame], onPage=paged_onpage_factory(draw_etf_page,   etfs_cons, ETF_PAGE_BG_IMG))
    etf_cons_news_t = PageTemplate(id="ETF_CONS_NEWS", frames=[frame], onPage=news_onpage_factory(etfs_cons))

    etf_mod_t       = PageTemplate(id="ETF_MOD",       frames=[frame], onPage=paged_onpage_factory(draw_etf_page,   etfs_mod,  ETF_PAGE_BG_IMG))
    etf_mod_news_t  = PageTemplate(id="ETF_MOD_NEWS",  frames=[frame], onPage=news_onpage_factory(etfs_mod))

    etf_agr_t       = PageTemplate(id="ETF_AGR",       frames=[frame], onPage=paged_onpage_factory(draw_etf_page,   etfs_agr,  ETF_PAGE_BG_IMG))
    etf_agr_news_t  = PageTemplate(id="ETF_AGR_NEWS",  frames=[frame], onPage=news_onpage_factory(etfs_agr))

    stk_mod_t       = PageTemplate(id="STK_MOD",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_mod, ETF_PAGE_BG_IMG))
    stk_mod_news_t  = PageTemplate(id="STK_MOD_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_mod))

    stk_arj_t       = PageTemplate(id="STK_ARJ",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_arj, ETF_PAGE_BG_IMG))
    stk_arj_news_t  = PageTemplate(id="STK_ARJ_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_arj))

    stk_opp_t       = PageTemplate(id="STK_OPP",       frames=[frame], onPage=paged_onpage_factory(draw_stock_page, stocks_opp, ETF_PAGE_BG_IMG))
    stk_opp_news_t  = PageTemplate(id="STK_OPP_NEWS",  frames=[frame], onPage=news_onpage_factory(stocks_opp))

    reit_cons_t      = PageTemplate(id="REIT_CONS",      frames=[frame], onPage=paged_onpage_factory(draw_reit_page,     reits_cons,    ETF_PAGE_BG_IMG))
    reit_cons_news_t = PageTemplate(id="REIT_CONS_NEWS", frames=[frame], onPage=news_onpage_factory(reits_cons))

    smcap_arj_t      = PageTemplate(id="SMCAP_ARJ",      frames=[frame], onPage=paged_onpage_factory(draw_smallcap_page, smallcaps_arj, ETF_PAGE_BG_IMG))
    smcap_arj_news_t = PageTemplate(id="SMCAP_ARJ_NEWS", frames=[frame], onPage=news_onpage_factory(smallcaps_arj))

    crp_t            = PageTemplate(id="CRP",            frames=[frame], onPage=paged_onpage_factory(draw_crypto_page,   crypto,        ETF_PAGE_BG_IMG))
    crp_news_t       = PageTemplate(id="CRP_NEWS",       frames=[frame], onPage=news_onpage_factory(crypto))

    hedge_t          = PageTemplate(id="HEDGE",          frames=[frame], onPage=paged_onpage_factory(draw_hedge_page,    hedge,         ETF_PAGE_BG_IMG))
    hedge_news_t     = PageTemplate(id="HEDGE_NEWS",     frames=[frame], onPage=news_onpage_factory(hedge))

   
    # ---------- Registrar templates ----------
    templates = [
        cover_t, news_t,
        perfilcons_t, perfilmod_t, perfilarj_t, perfilopp_t,
        etfs_cons_hdr, etfs_mod_hdr, etfs_arr_hdr,
        acao_mod_t, acao_arr_t,
        reits_hdr_t, small_hdr_t, crypto_hdr_t,
        etf_cons_t, etf_cons_news_t,
        etf_mod_t,  etf_mod_news_t,
        etf_agr_t,  etf_agr_news_t,
        stk_mod_t,  stk_mod_news_t,
        stk_arj_t,  stk_arj_news_t,
        stk_opp_t,  stk_opp_news_t,
        reit_cons_t, reit_cons_news_t,
        smcap_arj_t, smcap_arj_news_t,
        crp_t, crp_news_t,
        hedge_hdr_t, hedge_t, hedge_news_t,
        monthly_static_t,
        *monthly_templates,
        *custom_range_templates,
    ]
   
    doc.addPageTemplates(templates)
    # ---------- Helpers de Story ----------
    def add_bonds(story, items):
        if not items:
            return
        for i, b in enumerate(items):
            tid = f"BOND_{i}"

            def make_onpage(bond=b):
                def _onpage(c: Canvas, _doc):
                    draw_bond_page(c, bond)
                return _onpage

            doc.addPageTemplates([PageTemplate(id=tid, frames=[frame], onPage=make_onpage())])
            story.append(NextPageTemplate(tid))
            story.append(PageBreak())
            story.append(blank)
            
    def add_text_assets(story, items: list):
        """
        Cria um PageTemplate por item de text_assets e empilha no final.
        Evita depender de estado compartilhado (state['i']).
        """
        if not items:
            return

        for i, item in enumerate(items):
            tid = f"TEXT_ASSET_{i}"

            def make_onpage(cur=item):
                def _onpage(c: Canvas, _doc):
                    # 1) fundo
                    try:
                        onpage_text_asset(c, _doc)
                    except Exception as e:
                        print(f"[TEXT_ASSET] fundo: {e}")
                    # 2) conteúdo do item
                    try:
                        draw_text_asset_page(c, cur)
                    except Exception as e:
                        print(f"[TEXT_ASSET] item {i} erro: {e}")
                        # fallback visível
                        c.setFillColorRGB(1, 1, 1)
                        c.setFont("Helvetica-Oblique", 11)
                        c.drawString(60, 80, f"Falha ao renderizar TEXT_ASSET #{i}: {e}")
                return _onpage

            # registra template específico para ESTE item
            doc.addPageTemplates([PageTemplate(id=tid, frames=[frame], onPage=make_onpage())])

            # e agenda a página no Story
            story.append(NextPageTemplate(tid))
            story.append(PageBreak())
            story.append(blank)


    def add_asset_section(story, tpl_id: str, news_tpl_id: str, items: list):
        """
        Alterna: [Ativo] → [News] → [Ativo] … para cada item.
        """
        if not items:
            return
        story.append(NextPageTemplate(tpl_id))
        for _ in items:
            story.append(PageBreak()); story.append(blank)          # página do ativo
            story.append(NextPageTemplate(news_tpl_id))
            story.append(PageBreak()); story.append(blank)          # página de notícias
            story.append(NextPageTemplate(tpl_id))                  # volta para o template do ativo

    # ---------- Montagem do Story ----------
    Story = []
    # Notícias
    Story.append(NextPageTemplate("Noticias"))
    Story.append(PageBreak())
    Story.append(blank)

    # Perfil Conservador
    Story.append(NextPageTemplate("PerfilConservador"))
    Story.append(PageBreak())
    Story.append(blank)

    # BONDS
    add_bonds(Story, bonds)

    # REITs Conservadores
    if reits_cons:
        Story.append(NextPageTemplate("Reits_conservadores"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "REIT_CONS", "REIT_CONS_NEWS", reits_cons)

    # ETFs Conservadores
    if etfs_cons:
        Story.append(NextPageTemplate("Etfs_cons"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "ETF_CONS", "ETF_CONS_NEWS", etfs_cons)

    # Perfil Moderado
    Story.append(NextPageTemplate("PerfilModerado"))
    Story.append(PageBreak())
    Story.append(blank)

    # ETFs Moderados
    if etfs_mod:
        Story.append(NextPageTemplate("Etfs_mod"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "ETF_MOD", "ETF_MOD_NEWS", etfs_mod)

    # Ações Moderadas
    if stocks_mod:
        Story.append(NextPageTemplate("Acoes_moderadas"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "STK_MOD", "STK_MOD_NEWS", stocks_mod)

    # Perfil Arrojado
    Story.append(NextPageTemplate("PerfilArrojado"))
    Story.append(PageBreak())
    Story.append(blank)

    # ETFs Agressivos
    if etfs_agr:
        Story.append(NextPageTemplate("Etfs_arr"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "ETF_AGR", "ETF_AGR_NEWS", etfs_agr)

    # Ações Arrojadas
    if stocks_arj:
        Story.append(NextPageTemplate("Acoes_arrojadas"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "STK_ARJ", "STK_ARJ_NEWS", stocks_arj)

    
    # Oportunidades
    if stocks_opp:
        Story.append(NextPageTemplate("Oportunidade"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "STK_OPP", "STK_OPP_NEWS", stocks_opp)

    # Small Caps
    if smallcaps_arj:
        Story.append(NextPageTemplate("Small_caps"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "SMCAP_ARJ", "SMCAP_ARJ_NEWS", smallcaps_arj)

    # Hedge
    if hedge:
        Story.append(NextPageTemplate("HEDGE_HDR"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "HEDGE", "HEDGE_NEWS", hedge)

    
    # Crypto
    if crypto:
        Story.append(NextPageTemplate("Crypto"))
        Story.append(PageBreak())
        Story.append(blank)
        add_asset_section(Story, "CRP", "CRP_NEWS", crypto)

    # ===== PÁGINAS MENSAIS =====
    if _monthly_pages:
        # Página estática (header)
        Story.append(NextPageTemplate("MONTHLY_STATIC"))
        Story.append(PageBreak())
        Story.append(blank)
           
        # Adicionar cada página dinâmica com seu template específico
        for i, page_data in enumerate(_monthly_pages):
            template_id = f"MONTHLY_DYN_{i}"
            
            Story.append(NextPageTemplate(template_id))
            Story.append(PageBreak())
            Story.append(Paragraph("", styles["Normal"]))  # Conteúdo mínimo para ativar onPage
            
    # --- PÁGINAS AVULSAS: intervalos customizados (cards brancos) ---
    if custom_range_pages:
        Story.append(NextPageTemplate("CUSTOM_RANGE"))
        Story.append(PageBreak())
        Story.append(blank)

    # cria a página das trocas
    add_text_assets(Story, text_assets)

    # ---------- Render ----------
    doc.build(Story)
    buffer.seek(0)
    return buffer

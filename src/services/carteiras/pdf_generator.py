from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import os
from datetime import date
from datetime import datetime
import pytz
import locale
import tempfile

def is_safe_path(base_path: str, file_path: str) -> bool:
   
    if not file_path:
        return False
    try:
        abs_base = os.path.abspath(base_path)
        abs_file = os.path.abspath(file_path)
        return abs_file.startswith(abs_base)
    except (TypeError, ValueError):
        return False

def generate_pdf_buffer(
    investor: str,
    bonds: list = None,
    reits: list = None,
    stocks: list = None,
    etfs: list = None,
    etfs_op: list = None,
    etfs_af: list = None,
    hedge: list = None,
    opp_stocks: list = None,
    cryptos: list = None,
    real_estates: list = None,
    liquidity_value: float = 0.0
):
    
    bonds = bonds or []
    reits = reits or []
    stocks = stocks or []
    etfs = etfs or []
    etfs_op = etfs_op or []
    etfs_af = etfs_af or []
    opp_stocks = opp_stocks or []
    cryptos = cryptos or []
    real_estates = real_estates or []
    hedge = hedge or []
    buffer = BytesIO()
    
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='MainTitle', 
        fontSize=28, 
        alignment=1, 
        spaceAfter=20, 
        textColor=colors.HexColor('#1a365d'),
        fontName='Helvetica-Bold',
        leading=32
    ))
    
    styles.add(ParagraphStyle(
        name='SubTitle', 
        fontSize=18, 
        alignment=1, 
        spaceAfter=30,
        textColor=colors.HexColor('#2d3748'),
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='IntroText', 
        fontSize=12, 
        alignment=4, 
        spaceAfter=15,
        textColor=colors.HexColor('#4a5568'),
        leading=18,
        leftIndent=20,
        rightIndent=20
    ))
    
    styles.add(ParagraphStyle(
        name='HighlightBox', 
        fontSize=14, 
        alignment=1, 
        spaceAfter=20,
        textColor=colors.white,
        backColor=colors.HexColor('#3182ce'),
        borderColor=colors.HexColor('#2c5aa0'),
        borderWidth=1,
        leading=20,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=10
    ))
    
    styles.add(ParagraphStyle(
        name='SectionTitle', 
        fontSize=16, 
        leading=20, 
        spaceBefore=30, 
        spaceAfter=15, 
        textColor=colors.HexColor('#1a365d'),
        fontName='Helvetica-Bold',
        borderColor=colors.HexColor('#3182ce'),
        borderWidth=0,
        leftIndent=0
    ))
    
    styles.add(ParagraphStyle(
        name='AssetName', 
        fontSize=12, 
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='AssetDetail', 
        fontSize=10, 
        textColor=colors.HexColor('#4a5568'),
        leftIndent=20,
        spaceAfter=3
    ))
    
    styles.add(ParagraphStyle(
        name='DateStyle', 
        fontSize=10, 
        alignment=2, 
        textColor=colors.HexColor('#718096'),
        spaceAfter=30
    ))

    row_table_style = TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2d3748')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ])

    def calculate_total(items: list) -> float:
        """Calcula o valor total de uma lista de ativos."""
        if not isinstance(items, list):
            return 0.0
        return sum(item.get('investment', 0) or 0 for item in items if isinstance(item, dict))

    def format_value(value, is_percentage=False):
        """Formata valores numéricos para exibição."""
        if value is None or not isinstance(value, (int, float)):
            return '–'
        if is_percentage:
            if abs(value) <= 1:
                formatted_value = value * 100  
            else:
                formatted_value = value      
            return f"{formatted_value:.2f}%"  
        else:
            return f"${value:,.2f}"

    def get_growth_pct(s):
        try:
            target = s.get('target_price')
            unit_price = s.get('unit_price')
            
            if target and unit_price  != 0:
                return ((target / unit_price) - 1) * 100
        except (ZeroDivisionError, TypeError):
            return None
        return None

    def create_asset_card(item, asset_type):
        
        card_elements = []
        
        if asset_type == 'real_estates':
            name = item.get('symbol', 'Imóvel')
            card_elements.append(Paragraph(f"<b>{name}</b>", styles['AssetName']))
        else:
            name = item.get('company_name', item.get('name', '–'))
            symbol = item.get('symbol', '–')
            card_elements.append(Paragraph(f"<b>{name}</b> ({symbol})", styles['AssetName']))
        data_rows = []
        
        if asset_type == 'bonds':
            data_rows = [
                ['Código:', Paragraph(f"<font color='red'>{item.get('code', '–')}</font>", styles['AssetDetail'])],
                ['Vencimento:', Paragraph(item.get('maturity', '–'), styles['AssetDetail'])],
                ['Valor Unitário:', Paragraph(format_value(item.get('unit_price') or item.get('unitPrice')), styles['AssetDetail'])],
                ['Cupom:', Paragraph(format_value(item.get('coupon', 0), is_percentage=True), styles['AssetDetail'])],
                ['Quantidade:', Paragraph(str(item.get('quantity', '–')), styles['AssetDetail'])],
                ['Investimento:', Paragraph(format_value(item.get('investment')), styles['AssetDetail'])],
            ]
            
            description = item.get('description')
            if description and isinstance(description, list):
                desc_text = '<br/>'.join(description)
                data_rows.append(['Descrição:', Paragraph(desc_text, styles['AssetDetail'])])
        elif asset_type == 'reits':
            growth_pct = get_growth_pct(item)
            data_rows = [
                ['Setor:', item.get('sector', 'Real Estate')],
                ['Valor Atual:', format_value(item.get('unit_price'))],
                ['Entrada (EMA 10):', format_value(item.get('ema_10'))],
                ['Entrada (EMA 20):', format_value(item.get('ema_20'))],
                ['Score:', str(item.get('score', '–'))],
                ['Meta (Saída):', format_value(item.get('target_price'))],
                ['Dividend Yield:', format_value(item.get('dividend_yield', 0), is_percentage=True)],
                ['Quantidade:', str(item.get('quantity', '–'))],
                ['Investimento:', format_value(item.get('investment'))],
                ['Potencial Valorização:', format_value(growth_pct, is_percentage=True) if growth_pct else '–'],
            ]

        elif asset_type == 'stocks' or asset_type == 'opp_stocks':
            growth_pct = get_growth_pct(item)
            data_rows = [
                ['Setor:', item.get('sector', 'Indefinido')],
                ['Valor Atual:', format_value(item.get('unit_price'))],
                ['Entrada (EMA 10):', format_value(item.get('ema_10'))],
                ['Entrada (EMA 20):', format_value(item.get('ema_20'))],
                ['Score:', str(item.get('score', '–'))],
                ['Meta (Saída):', format_value(item.get('target_price'))],
                ['Dividend Yield:', format_value(item.get('dividend_yield', 0), is_percentage=True)],
                ['Quantidade:', str(item.get('quantity', '–'))],
                ['Investimento:', format_value(item.get('investment'))],
                ['Potencial Valorização:', format_value(growth_pct, is_percentage=True) if growth_pct else '–'],
            ]
        elif asset_type in ['etfs', 'etfs_op', 'etfs_af', 'hedge'] or 'etf' in asset_type:
            entry_field = 'antifragile_entry_price' if 'af' in asset_type else 'ema_20'
            entry_label = 'Entrada (Anti-Frágil):' if 'af' in asset_type else 'Entrada (EMA 20):'
            data_rows = [
                ['Valor Atual:', format_value(item.get('unit_price'))],
                [entry_label, format_value(item.get(entry_field))],
                ['Dividend Yield:', format_value(item.get('dividend_yield', 0), is_percentage=True)],
                ['Quantidade:', str(item.get('quantity', '–'))],
                ['Investimento:', format_value(item.get('investment'))],
                ['Crescimento Médio Anual:', format_value(item.get('average_growth', 0), is_percentage=True)],
            ]

        elif asset_type == 'cryptos':
            quantity_text = f"{item.get('quantity', 0):.8f}".rstrip('0').rstrip('.') if item.get('quantity') is not None else '–'
            data_rows = [
                ['Valor Atual:', format_value(item.get('unit_price'))],
                ['Quantidade:', quantity_text],
                ['Investimento:', format_value(item.get('investment'))],
                ['Valorização Média:', f"{item.get('average_growth', 0):.2f}%" if item.get('average_growth') else '–'],
            ]
        elif asset_type == 'real_estates':
            data_rows = [
                ['Valor Investido:', format_value(item.get('investment'))],
                ['Valorização:', format_value(item.get('appreciation_pct', 0), is_percentage=True)],
                ['Valor Atual:', format_value(item.get('current_value'))],
            ]
        
        if data_rows:
            has_description = any('Descrição:' in str(row[0]) for row in data_rows)
            if has_description:
                table = Table(data_rows, colWidths=[1.5*inch, 4*inch])
            else:
                table = Table(data_rows, colWidths=[2*inch, 2*inch])
            table.setStyle(row_table_style)
            card_elements.append(table)
            card_elements.append(Spacer(1, 10))  
        
        if asset_type in ['stocks', 'opp_stocks']:
            sector = item.get('sector', 'Indefinido')
            ema_10 = format_value(item.get('ema_10'))
            ema_20 = format_value(item.get('ema_20'))
            target_price = format_value(item.get('target_price'))
            dividend_yield_text = format_value(item.get('dividend_yield', 0), is_percentage=True)
            
            analysis = f"""A ação <b>{symbol}</b> do setor <b>{sector}</b> tem entrada recomendada 
                        para um perfil moderado em <b>{ema_20}</b> e entrada recomendada para 
                        um perfil agressivo em <b>{ema_10}.</b> Com expectativa de atingir <b>{target_price}</b>. 
                        Dividend yield anual de <b>{dividend_yield_text}</b>."""
            
            card_elements.append(Paragraph(analysis, styles['AssetDetail']))
            card_elements.append(Spacer(1, 20))

        elif asset_type == 'reits':
            sector = item.get('sector', 'Real Estate')
            ema_10 = format_value(item.get('ema_10'))
            ema_20 = format_value(item.get('ema_20'))
            target_price = format_value(item.get('target_price'))
            dividend_yield_text = format_value(item.get('dividend_yield', 0), is_percentage=True)
            
            analysis = f"""O REIT <b>{symbol}</b> do setor <b>{sector}</b> tem entrada recomendada 
                        para um perfil moderado em <b>{ema_20}</b> e entrada recomendada para 
                        um perfil agressivo em <b>{ema_10}.</b> Com expectativa de atingir <b>{target_price}</b>. 
                        Distribuição anual de dividendos de <b>{dividend_yield_text}</b>."""
            
            card_elements.append(Paragraph(analysis, styles['AssetDetail']))
            card_elements.append(Spacer(1, 20))

        chart_path = item.get('chart')
        if chart_path and is_safe_path('.', chart_path) and os.path.exists(chart_path):
            card_elements.append(Spacer(1, 20))  # 20px antes do gráfico
            card_elements.append(Image(chart_path, width=6*inch, height=3*inch))
            card_elements.append(Spacer(1, 10))  # 10px após o gráfico

        card_elements.append(Spacer(1, 0.3 * inch))
        return card_elements

    def add_asset_section(elements, title, total, assets, asset_type):
        """Adiciona uma seção de ativos com layout em cards."""
        if not assets:
            return
        
        elements.append(Paragraph(f"{title}", styles['SectionTitle']))
        
        total_box = f"<b>Investimento Total: {format_value(total)}</b>"
        elements.append(Paragraph(total_box, styles['HighlightBox']))
        
        for item in assets:
            if not isinstance(item, dict):
                continue
            
            asset_card = create_asset_card(item, asset_type)
            
            card_group = KeepTogether(asset_card)
            elements.append(card_group)

    total_value = (
        calculate_total(bonds) + calculate_total(stocks) + calculate_total(etfs)  +
        calculate_total(etfs_op) + calculate_total(etfs_af) +
        calculate_total(opp_stocks) + calculate_total(cryptos) +
        calculate_total(real_estates) + calculate_total(reits) + calculate_total(hedge) + (liquidity_value or 0.0)
    )

    elements = []
    elements.append(Paragraph("🏦 BELLA INVESTIMENTOS", styles['MainTitle']))
    elements.append(Paragraph(f"Relatório de Carteira - {investor}", styles['SubTitle']))
    total_highlight = f"""
        <b>Valor Total da Carteira: {format_value(total_value)}</b><br/>
        <i>Carteira estruturada em dólares americanos</i>
    """
    elements.append(Paragraph(total_highlight, styles['HighlightBox']))
    
    intro_text = f"""
        Este relatório apresenta uma análise detalhada da sua carteira de investimentos, 
        cuidadosamente estruturada de acordo com seu perfil de risco e objetivos financeiros. 
        Nossa estratégia prioriza a <b>diversificação inteligente</b> e o <b>crescimento sustentável</b> 
        do seu patrimônio.
    """
    elements.append(Paragraph(intro_text, styles['IntroText']))
    
    instructions_text = """
        📝 <b>Como utilizar este relatório:</b><br/>
        • Os códigos dos ativos estão destacados em <font color='red'><b>vermelho</b></font> para facilitar a busca na sua corretora<br/>
        • As entradas recomendadas são baseadas em médias móveis (EMA 10 e EMA 20) para ações e ETFs<br/>
        • As metas de saída representam potencial de valorização baseado em análise fundamentalista
    """
    elements.append(Paragraph(instructions_text, styles['IntroText']))
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    now_brasilia = datetime.now(brasilia_tz)
    data_hora = now_brasilia.strftime('%d/%m/%Y às %H:%M')
    elements.append(Paragraph(f"Data do relatório: {data_hora}", styles['DateStyle']))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(PageBreak())
    
    if bonds:
        add_asset_section(elements, '💰 Títulos de Renda Fixa (Bonds)', calculate_total(bonds), bonds, 'bonds')
        elements.append(PageBreak())

    if reits:
        add_asset_section(elements, '🏢 REITs', calculate_total(reits), reits, 'reits')
        elements.append(PageBreak())

    if stocks:
        add_asset_section(elements, '📈 Ações', calculate_total(stocks), stocks, 'stocks')
        elements.append(PageBreak())
    
    if opp_stocks:
        add_asset_section(elements, '🎯 Ações de Oportunidade', calculate_total(opp_stocks), opp_stocks, 'opp_stocks')
        elements.append(PageBreak())

    if etfs:
        add_asset_section(elements, '📊 ETFs', calculate_total(etfs), etfs, 'etfs')
        elements.append(PageBreak())

    if etfs_op:
        add_asset_section(elements, '🚀 ETFs de Oportunidade', calculate_total(etfs_op), etfs_op, 'etfs_op')
        elements.append(PageBreak())
    
    if etfs_af:
        add_asset_section(elements, '🛡️ ETFs Anti-Frágil', calculate_total(etfs_af), etfs_af, 'etfs_af')
        elements.append(PageBreak())
        
    if hedge:
        add_asset_section(elements, '🛡️ Hedge', calculate_total(hedge), hedge, 'hedge')
        elements.append(PageBreak())

    if cryptos:
        add_asset_section(elements, '₿ Criptomoedas', calculate_total(cryptos), cryptos, 'cryptos')
        elements.append(PageBreak())

    if real_estates:
        add_asset_section(elements, '🏠 Imóveis', calculate_total(real_estates), real_estates, 'real_estates')
       
        # ---- Seção própria de Liquidez (valor único) ----
    if liquidity_value and liquidity_value > 0:
        elements.append(Paragraph('💧 Liquidez', styles['SectionTitle']))

        # destaque com o valor de liquidez
        elements.append(Paragraph(f"<b>Total de Liquidez: {format_value(liquidity_value)}</b>", styles['HighlightBox']))

        # tabelinha 'Liquidez | Valor' com uma linha só
        
        data = [["Liquidez", "Valor"], ["Disponível", format_value(liquidity_value)]]
        t = Table(data, colWidths=[3.0*inch, 3.0*inch], hAlign="CENTER", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF2FF")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#0F2B5B")),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,0), 10),
            ("ALIGN",      (0,0), (-1,0), "CENTER"),
            ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",   (0,1), (-1,-1), 9),
            ("ALIGN",      (1,1), (1,-1), "RIGHT"),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
            ("BOX",        (0,0), (-1,-1), 0.5, colors.HexColor("#D9E4F5")),
            ("INNERGRID",  (0,0), (-1,-1), 0.25, colors.HexColor("#D9E4F5")),
            ("LEFTPADDING",(0,0), (-1,-1), 6),
            ("RIGHTPADDING",(0,0),(-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6))

        elements.append(PageBreak())


    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=0.7*inch, leftMargin=0.7*inch,
                            topMargin=0.7*inch, bottomMargin=0.7*inch)
    doc.build(elements)
    buffer.seek(0)
    return buffer
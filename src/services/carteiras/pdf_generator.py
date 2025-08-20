from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image
)
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import os
from datetime import date
import locale
import tempfile

def is_safe_path(base_path: str, file_path: str) -> bool:
    """Verifica se o caminho do arquivo está dentro do diretório base."""
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
    stocks: list = None,
    etfs: list = None,
    etfs_op: list = None,
    etfs_af: list = None,
    opp_stocks: list = None,
    cryptos: list = None,
    real_estates: list = None
):
    """
    Gera um relatório de carteira de investimentos em formato PDF.
    """
    bonds = bonds or []
    stocks = stocks or []
    etfs = etfs or []
    etfs_op = etfs_op or []
    etfs_af = etfs_af or []
    opp_stocks = opp_stocks or []
    cryptos = cryptos or []
    real_estates = real_estates or []

    buffer = BytesIO()
    
    # === Definição de Estilos para ReportLab ===
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleStyle', fontSize=18, alignment=1, spaceAfter=10, textColor=colors.blue))
    styles.add(ParagraphStyle(name='SubtitleStyle', fontSize=14, alignment=1, spaceAfter=20))
    styles.add(ParagraphStyle(name='MyHeading2', fontSize=14, leading=16, spaceBefore=20, spaceAfter=10, textColor=colors.black))
    styles.add(ParagraphStyle(name='NormalJustify', alignment=4, spaceAfter=10))
    styles.add(ParagraphStyle(name='Bold', fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SmallParagraph', fontSize=8, spaceAfter=5, leading=10, alignment=4))
    wrap_style = ParagraphStyle(name='WrapStyle', fontSize=9, leading=11, wordWrap='CJK')

    
    table_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4f4f4')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ])

    total_row_style = TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
    ])

    # === Funções Auxiliares ===
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
            formatted_value = value * 100
            if formatted_value >= 10:
                return f"{formatted_value:.2f}%"
            else:
                return f"{formatted_value:.1f}%"
        else:
            return f"${value:,.2f}"

    def get_growth_pct(s):
        try:
            target = s.get('target_price')
            unit_price = s.get('unit_price')
            if target and unit_price and unit_price != 0:
                return ((target / unit_price) - 1)
        except (ZeroDivisionError, TypeError):
            return None
        return None

    def add_asset_section(elements, title, total, assets, headers, col_widths_template, is_stock=True):
        if not assets:
            return
        elements.append(Paragraph(f"{title}: USD {format_value(total, False)}", styles['MyHeading2']))

        asset_data = [headers]
        for item in assets:
            if not isinstance(item, dict):
                continue
            
            row = []
            if 'imoveis' in title.lower():
                row = [
                    Paragraph(item.get('symbol', '–'), wrap_style),
                    Paragraph(format_value(item.get('investment')), wrap_style),
                    Paragraph(format_value(item.get('appreciation_pct', 0), is_percentage=True), wrap_style),
                    Paragraph(format_value(item.get('current_value')), wrap_style)
                ]
            elif 'criptomoedas' in title.lower():
                quantity_text = f"{item.get('quantity', 0):.8f}".rstrip('0').rstrip('.') if item.get('quantity') is not None else '–'
                growth_text = f"{item.get('average_growth', 0):.2f}" if item.get('average_growth') is not None else '–'
                row = [
                    Paragraph(item.get('company_name', '–'), wrap_style),
                    Paragraph(item.get('symbol', '–'), wrap_style),
                    Paragraph(format_value(item.get('unit_price')), wrap_style),
                    Paragraph(quantity_text, wrap_style),
                    Paragraph(format_value(item.get('investment')), wrap_style),
                    Paragraph(growth_text, wrap_style)
                ]
            elif is_stock:
                growth_pct = get_growth_pct(item)
                row = [
                    Paragraph(item.get('company_name', '–'), wrap_style),
                    Paragraph('D + 1', wrap_style),
                    Paragraph(item.get('symbol', '–'), wrap_style),
                    Paragraph(format_value(item.get('unit_price')), wrap_style),
                    Paragraph(format_value(item.get('ema_20')), wrap_style),
                    Paragraph(format_value(item.get('target_price')), wrap_style),
                    Paragraph(format_value(item.get('dividend_yield', 0), is_percentage=True), wrap_style),
                    Paragraph(str(item.get('quantity', '–')), wrap_style),
                    Paragraph(format_value(item.get('investment')), wrap_style),
                    Paragraph(format_value(growth_pct, is_percentage=True), wrap_style)
                ]
            elif 'etf' in title.lower():
                row = [
                    Paragraph(item.get('company_name', '–'), wrap_style),
                    Paragraph('D + 1', wrap_style),
                    Paragraph(item.get('symbol', '–'), wrap_style),
                    Paragraph(format_value(item.get('unit_price')), wrap_style),
                    Paragraph(format_value(item.get('ema_20') if 'antifragil' not in title.lower() else item.get('antifragile_entry_price')), wrap_style),
                    Paragraph(format_value(item.get('dividend_yield', 0), is_percentage=True), wrap_style),
                    Paragraph(str(item.get('quantity', '–')), wrap_style),
                    Paragraph(format_value(item.get('investment')), wrap_style),
                    Paragraph(format_value(item.get('average_growth', 0), is_percentage=True), wrap_style)
                ]
            else: # bonds
                row = [
                    Paragraph(f"{item.get('name', '')} – cod <font color='red'>{item.get('code', '')}</font>", wrap_style),
                    Paragraph(item.get('maturity', '–'), wrap_style),
                    Paragraph(format_value(item.get('unit_price') or item.get('unitPrice')), wrap_style),
                    Paragraph(format_value(item.get('coupon', 0), is_percentage=True), wrap_style),
                    Paragraph(str(item.get('quantity', '–')), wrap_style),
                    Paragraph(format_value(item.get('investment')), wrap_style)
                ]
            
            asset_data.append(row)

        asset_data.append(
            ['Total ' + title] 
            + [''] * (len(asset_data[0]) - 2)  # preenche o meio com vazios
            + [f"USD {format_value(total, False)}"]  # última coluna com o total
        )
        
        table = Table(asset_data)
        table.setStyle(table_style)
        table.setStyle(total_row_style)
        table.setStyle(TableStyle([('SPAN', (0, -1), (len(headers) - 2, -1))]))
        elements.append(table)
        
        elements.append(Paragraph(f"Resumo dos {title}", styles['MyHeading2']))
        for item in assets:
            if not isinstance(item, dict): continue
            
            symbol = item.get('symbol', '')
            sector = item.get('sector', 'Indefinido')
            ema_20 = format_value(item.get('ema_20'))
            target_price = format_value(item.get('target_price'))
            dividend_yield_text = format_value(item.get('dividend_yield', 0), is_percentage=True)
            
            if is_stock:
                elements.append(Paragraph(f"""
                    A ação <strong>{symbol}</strong> pertence ao setor de <strong>{sector}</strong>,
                    o preço ideal de entrada é <strong>USD {ema_20}</strong>,
                    e possui uma expectativa que alcance <strong>USD {target_price}</strong>.
                    Distribuindo dividendos anuais de {dividend_yield_text}.
                """, styles['NormalJustify']))
            else:
                growth_text = "dados históricos insuficientes"
                avg_growth = item.get('average_growth')
                if avg_growth is not None:
                    growth_text = f"crescimento médio anual de {format_value(avg_growth, is_percentage=True)} com base nos últimos 10 anos"
                
                elements.append(Paragraph(f"""
                    <strong>{symbol}</strong> – {item.get('company_name', '')} possui um
                    dividend yield de {dividend_yield_text} ao ano, o preço ideal de entrada é <strong>USD {ema_20}</strong>,
                    e {growth_text}.
                """, styles['NormalJustify']))
            
            chart_path = item.get('chart')
            if chart_path and is_safe_path('.', chart_path) and os.path.exists(chart_path):
                elements.append(Image(chart_path, width=6*inch, height=3*inch))
            elements.append(Spacer(1, 0.2 * inch))

    # === Dados para o PDF ===
    total_value = (
        calculate_total(bonds) + calculate_total(stocks) + calculate_total(etfs) +
        calculate_total(etfs_op) + calculate_total(etfs_af) +
        calculate_total(opp_stocks) + calculate_total(cryptos) +
        calculate_total(real_estates)
    )

    data = {
        'investor': investor,
        'date': date.today().strftime("%d/%m/%Y"),
        'total_value': total_value,
        'bonds_total': calculate_total(bonds),
        'stocks_total': calculate_total(stocks),
        'etfs_total': calculate_total(etfs),
        'etfs_op_total': calculate_total(etfs_op),
        'etfs_af_total': calculate_total(etfs_af),
        'opp_stocks_total': calculate_total(opp_stocks),
        'cryptos_total': calculate_total(cryptos),
        'real_estates_total': calculate_total(real_estates),
        'bonds': bonds, 'stocks': stocks, 'etfs': etfs,
        'etfs_op': etfs_op, 'etfs_af': etfs_af,
        'opp_stocks': opp_stocks, 'cryptos': cryptos,
        'real_estates': real_estates,
    }

    # === Construção do conteúdo do PDF ===
    elements = []

    elements.append(Paragraph("Bella Investimentos", styles['TitleStyle']))
    elements.append(Paragraph(f"Carteira {data['investor']}", styles['SubtitleStyle']))
    elements.append(Paragraph(f"""
        A proposta é baseada em uma carteira em dólares, no valor de <strong>USD {format_value(data['total_value'])}</strong>.
        A alocação dos ativos foi cuidadosamente estruturada de acordo com o seu perfil de investidor,
        priorizando a valorização e a preservação de capital.
    """, styles['NormalJustify']))
    elements.append(Paragraph("""
        Para facilitar a compra dos ativos na sua corretora, destacamos em vermelho os códigos dos ativos,
        tornando mais simples a pesquisa e execução das ordens.
    """, styles['NormalJustify']))
    elements.append(Paragraph(f"Data do relatório: {data['date']}", styles['Normal']))

    # --- Seções de Ativos ---
    add_asset_section(elements, 'Bonds', data['bonds_total'], data['bonds'],
                      ['Nome', 'Vencimento', 'Valor Unid.', 'Cupom', 'Qtd.', 'Investimento'],
                      [1*inch, 1*inch, 1*inch, 0.7*inch, 0.7*inch, 1*inch], is_stock=False)

    add_asset_section(elements, 'Ações', data['stocks_total'], data['stocks'],
                      ['Ação', 'Tempo', 'Código', 'Valor atual', 'Entrada', 'Saída', 'Div %', 'Qtd.', 'Invest.', 'Valorização'],
                      [1*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.5*inch, 0.5*inch, 0.7*inch, 0.8*inch], is_stock=True)
    
    add_asset_section(elements, 'Ações de Oportunidade', data['opp_stocks_total'], data['opp_stocks'],
                      ['Ação', 'Tempo', 'Código', 'Valor atual', 'Entrada', 'Saída', 'Div %', 'Qtd.', 'Invest.', 'Valorização'],
                      [1*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.5*inch, 0.5*inch, 0.7*inch, 0.8*inch], is_stock=True)

    add_asset_section(elements, 'ETFs', data['etfs_total'], data['etfs'],
                      ['ETF', 'Tempo', 'Código', 'Valor atual', 'Entrada', 'Div %', 'Qtd.', 'Investimento', 'Cresc. Anual'],
                      [1*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.5*inch, 0.7*inch, 0.9*inch], is_stock=False)

    add_asset_section(elements, 'ETFs de Oportunidade', data['etfs_op_total'], data['etfs_op'],
                      ['ETF', 'Tempo', 'Código', 'Valor atual', 'Entrada', 'Div %', 'Qtd.', 'Investimento', 'Cresc. Anual'],
                      [1*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.5*inch, 0.7*inch, 0.9*inch], is_stock=False)
    
    add_asset_section(elements, 'ETFs Anti-Frágil', data['etfs_af_total'], data['etfs_af'],
                      ['ETF', 'Tempo', 'Código', 'Valor atual', 'Entrada (Anti-Frágil)', 'Div %', 'Qtd.', 'Investimento', 'Cresc. Anual'],
                      [1*inch, 0.5*inch, 0.7*inch, 0.7*inch, 1.2*inch, 0.6*inch, 0.5*inch, 0.7*inch, 0.9*inch], is_stock=False)

    if data['cryptos']:
        elements.append(Paragraph("Criptomoedas", styles['MyHeading2']))
        cryptos_data = [
            ['Nome', 'Código', 'Valor atual', 'Qtd.', 'Investimento', 'Valorização (%)']
        ]
        for c in data['cryptos']:
            if not isinstance(c, dict): continue
            
            quantity_text = f"{c.get('quantity', 0):.8f}".rstrip('0').rstrip('.') if c.get('quantity') is not None else '–'
            growth_text = f"{c.get('average_growth', 0):.2f}" if c.get('average_growth') is not None else '–'
            
            cryptos_data.append([
                c.get('company_name', '–'),
                c.get('symbol', '–'),
                format_value(c.get('unit_price')),
                quantity_text,
                format_value(c.get('investment')),
                growth_text
            ])
        
        cryptos_data.append(['Total Criptomoedas', '', '', '', '', f"USD {format_value(data['cryptos_total'], False)}"])
        cryptos_table = Table(cryptos_data, colWidths=['*', 1*inch, 1*inch, 0.7*inch, 1*inch, 1.2*inch])
        cryptos_table.setStyle(table_style)
        cryptos_table.setStyle(total_row_style)
        cryptos_table.setStyle(TableStyle([('SPAN', (0, -1), (4, -1))]))
        elements.append(cryptos_table)
        elements.append(Spacer(1, 0.2 * inch))

    if data['real_estates']:
        elements.append(Paragraph(f"Imóveis: USD {format_value(data['real_estates_total'], False)}", styles['MyHeading2']))
        real_estates_data = [
            ['Imóvel - nome', 'Valor investido', 'Valorização (%)', 'Valor esperado']
        ]
        for r in data['real_estates']:
            if not isinstance(r, dict): continue
            real_estates_data.append([
                r.get('symbol', '–'),
                format_value(r.get('investment')),
                format_value(r.get('appreciation_pct', 0), is_percentage=True),
                format_value(r.get('current_value'))
            ])
        
        real_estates_data.append(['Total Imóveis', '', '', f"USD {format_value(data['real_estates_total'], False)}"])
        real_estates_table = Table(real_estates_data, colWidths=['*', 1.5*inch, 1.5*inch, 1.5*inch])
        real_estates_table.setStyle(table_style)
        real_estates_table.setStyle(total_row_style)
        real_estates_table.setStyle(TableStyle([('SPAN', (0, -1), (2, -1))]))
        elements.append(real_estates_table)
        elements.append(Spacer(1, 0.2 * inch))

    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    doc.build(elements)
    buffer.seek(0)
    return buffer
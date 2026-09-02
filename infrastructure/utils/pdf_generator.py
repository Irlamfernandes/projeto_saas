import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def gerar_extrato_pdf_cliente(cliente, caminho_arquivo):
    doc = SimpleDocTemplate(caminho_arquivo, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle(
        'TituloLoja',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=2
    )
    
    subtitulo_style = ParagraphStyle(
        'SubTitulo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=15
    )

    loja_nome = cliente.loja.nome_loja if hasattr(cliente.loja, 'nome_loja') else "Minha Loja"
    story.append(Paragraph(f"<b>{loja_nome}</b>", titulo_style))
    story.append(Paragraph(f"Extrato Oficial de Conta / Caderneta", subtitulo_style))
    
    story.append(Paragraph(f"<b>Cliente:</b> {cliente.nome}", styles['Normal']))
    story.append(Paragraph(f"<b>Telefone:</b> {cliente.telefone or 'Não informado'}", styles['Normal']))
    story.append(Spacer(1, 10))

    # Situação Financeira Oficial (Auditada pelo sistema)
    saldo = cliente.saldo_geral
    if saldo > 0:
        status_texto = f"Situação: DEVENDO R$ {saldo:.2f} (Valor Pendente)"
        cor_status = colors.HexColor('#dc2626')
    elif saldo < 0:
        status_texto = f"Situação: CRÉDITO DE R$ {abs(saldo):.2f} (Valor a mais)"
        cor_status = colors.HexColor('#16a34a')
    else:
        status_texto = "Situação: TUDO CERTO (Conta Quitado / Sem Saldo Pendente)"
        cor_status = colors.HexColor('#4b5563')

    resumo_style = ParagraphStyle(
        'ResumoFinanceiro',
        parent=styles['Normal'],
        fontSize=11,
        textColor=cor_status,
        spaceAfter=15,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph(status_texto, resumo_style))
    story.append(Spacer(1, 5))

    # Últimas 5 Compras Automáticas (Regra fixa anti-fraude)
    story.append(Paragraph("<b>Últimas 5 Compras Registradas no Sistema:</b>", styles['Heading3']))
    story.append(Spacer(1, 5))

    vendas_ultimas = cliente.vendas.all().order_by('-data_venda')[:5]
    
    dados_tabela = [["Data", "Descrição dos Produtos", "Total (R$)"]]
    for venda in vendas_ultimas:
        data_str = venda.data_venda.strftime('%d/%m/%Y %H:%M')
        itens_desc = ", ".join([f"{item.quantidade}x {item.produto.nome}" for item in venda.itens.all()])
        valor_str = f"R$ {venda.valor_total:.2f}"
        dados_tabela.append([data_str, itens_desc, valor_str])

    if len(vendas_ultimas) == 0:
        dados_tabela.append(["-", "Nenhuma compra registrada", "-"])

    tabela_compras = Table(dados_tabela, colWidths=[100, 320, 115])
    tabela_compras.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(tabela_compras)
    doc.build(story)
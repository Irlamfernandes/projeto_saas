from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import openpyxl

def gerar_relatorio_pdf_secao(tipo_secao, contexto_dados, caminho_arquivo):
    doc = SimpleDocTemplate(caminho_arquivo, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1f2937'), spaceAfter=10)
    
    if tipo_secao == 'resumo' or tipo_secao == 'geral':
        story.append(Paragraph("<b>Resumo Executivo e Indicadores</b>", titulo_style))
        story.append(Spacer(1, 10))
        dados = [
            ["Indicador", "Valor"],
            ["Faturamento Total", f"R$ {contexto_dados['total_geral_vendas']:.2f}"],
            ["Ticket Médio", f"R$ {contexto_dados['ticket_medio']:.2f}"],
            ["Total a Receber (Fiado)", f"R$ {contexto_dados['total_fiado_pendente']:.2f}"],
            ["Crédito de Clientes", f"R$ {contexto_dados['total_credito_clientes']:.2f}"],
        ]
        t = Table(dados, colWidths=[200, 312])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(t)
        story.append(Spacer(1, 15))

    elif tipo_secao == 'temporal':
        story.append(Paragraph("<b>Desempenho por Ciclo Temporal</b>", titulo_style))
        story.append(Spacer(1, 10))
        dados = [
            ["Período", "Faturamento"],
            ["Hoje", f"R$ {contexto_dados['vendas_hoje_valor']:.2f}"],
            ["Esta Semana", f"R$ {contexto_dados['vendas_semana_valor']:.2f}"],
            ["Este Mês", f"R$ {contexto_dados['vendas_mes_valor']:.2f}"],
            ["Este Ano", f"R$ {contexto_dados['vendas_ano_valor']:.2f}"],
        ]
        t = Table(dados, colWidths=[200, 312])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(t)

    elif tipo_secao == 'devendo':
        story.append(Paragraph("<b>Relatório de Clientes Devendo (Fiado)</b>", titulo_style))
        story.append(Spacer(1, 10))
        dados = [["Cliente", "Valor Devido"]]
        for cliente in contexto_dados['clientes_devendo']:
            dados.append([cliente.nome, f"R$ {cliente.saldo_geral:.2f}"])
        t = Table(dados, colWidths=[300, 212])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(t)

    elif tipo_secao == 'credito':
        story.append(Paragraph("<b>Relatório de Clientes com Crédito</b>", titulo_style))
        story.append(Spacer(1, 10))
        dados = [["Cliente", "Crédito Disponível"]]
        for cliente in contexto_dados['clientes_credito']:
            dados.append([cliente.nome, f"R$ {abs(cliente.saldo_geral):.2f}"])
        t = Table(dados, colWidths=[300, 212])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(t)

    elif tipo_secao == 'estoque':
        story.append(Paragraph("<b>Inventário de Estoque Completo</b>", titulo_style))
        story.append(Spacer(1, 10))
        dados_estoque = [["Produto", "Preço (R$)", "Qtd em Estoque"]]
        for prod in contexto_dados['estoque_ordenado']:
            dados_estoque.append([prod.nome, f"R$ {prod.preco_venda:.2f}", str(prod.quantidade_estoque)])
        
        t_est = Table(dados_estoque, colWidths=[250, 130, 132])
        t_est.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(t_est)

    doc.build(story)


def gerar_relatorio_excel_secao(tipo_secao, contexto_dados, caminho_arquivo):
    wb = openpyxl.Workbook()
    ws = wb.active
    
    if tipo_secao == 'resumo':
        ws.title = "Resumo Executivo"
        ws.append(["Métrica", "Valor (R$)"])
        ws.append(["Faturamento Total", float(contexto_dados['total_geral_vendas'])])
        ws.append(["Ticket Médio", float(contexto_dados['ticket_medio'])])
        ws.append(["Total a Receber", float(contexto_dados['total_fiado_pendente'])])
        ws.append(["Crédito de Clientes", float(contexto_dados['total_credito_clientes'])])
        
    elif tipo_secao == 'estoque':
        ws.title = "Estoque"
        ws.append(["Produto", "Preço de Venda", "Quantidade em Estoque"])
        for prod in contexto_dados['estoque_ordenado']:
            ws.append([prod.nome, float(prod.preco_venda), prod.quantidade_estoque])
            
    elif tipo_secao == 'devendo':
        ws.title = "Clientes Devendo"
        ws.append(["Cliente", "Valor Devido"])
        for cliente in contexto_dados['clientes_devendo']:
            ws.append([cliente.nome, float(cliente.saldo_geral)])

    elif tipo_secao == 'credito':
        ws.title = "Clientes com Crédito"
        ws.append(["Cliente", "Crédito Disponível"])
        for cliente in contexto_dados['clientes_credito']:
            ws.append([cliente.nome, float(abs(cliente.saldo_geral))])
            
    else: # Geral / Tudo
        ws.title = "Resumo"
        ws.append(["Métrica", "Valor (R$)"])
        ws.append(["Faturamento Total", float(contexto_dados['total_geral_vendas'])])
        ws.append(["Total a Receber", float(contexto_dados['total_fiado_pendente'])])
        
        ws2 = wb.create_sheet(title="Estoque")
        ws2.append(["Produto", "Preço", "Quantidade"])
        for prod in contexto_dados['estoque_ordenado']:
            ws2.append([prod.nome, float(prod.preco_venda), prod.quantidade_estoque])

        ws3 = wb.create_sheet(title="Clientes Devendo")
        ws3.append(["Cliente", "Valor Devido"])
        for cliente in contexto_dados['clientes_devendo']:
            ws3.append([cliente.nome, float(cliente.saldo_geral)])

    wb.save(caminho_arquivo)

gerar_relatorio_pdf = gerar_relatorio_pdf_secao
gerar_relatorio_excel = gerar_relatorio_excel_secao
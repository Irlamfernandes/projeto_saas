from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.core.exceptions import PermissionDenied
import openpyxl

# Constantes para eliminar duplicações literais apontadas pelo SonarQube
ABA_CLIENTES_DEVENDO = "Clientes Devendo"
ABA_ESTOQUE = "Estoque"
ABA_CREDITO = "Clientes com Crédito"


def _criar_tabela_padrao(dados, col_widths):
    """Cria e estiliza tabelas do PDF uniformemente."""
    t = Table(dados, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    return t


def _adicionar_secao_resumo(story, contexto_dados, titulo_style):
    story.append(Paragraph("<b>Resumo Executivo e Indicadores</b>", titulo_style))
    story.append(Spacer(1, 10))
    dados = [
        ["Indicador", "Valor"],
        ["Faturamento Total", f"R$ {contexto_dados.get('total_geral_vendas', 0):.2f}"],
        ["Ticket Médio", f"R$ {contexto_dados.get('ticket_medio', 0):.2f}"],
        ["Total a Receber (Fiado)", f"R$ {contexto_dados.get('total_fiado_pendente', 0):.2f}"],
        ["Crédito de Clientes", f"R$ {contexto_dados.get('total_credito_clientes', 0):.2f}"],
    ]
    story.append(_criar_tabela_padrao(dados, [200, 312]))
    story.append(Spacer(1, 15))


def _adicionar_secao_temporal(story, contexto_dados, titulo_style):
    story.append(Paragraph("<b>Desempenho por Ciclo Temporal</b>", titulo_style))
    story.append(Spacer(1, 10))
    dados = [
        ["Período", "Faturamento"],
        ["Hoje", f"R$ {contexto_dados.get('vendas_hoje_valor', 0):.2f}"],
        ["Esta Semana", f"R$ {contexto_dados.get('vendas_semana_valor', 0):.2f}"],
        ["Este Mês", f"R$ {contexto_dados.get('vendas_mes_valor', 0):.2f}"],
        ["Este Ano", f"R$ {contexto_dados.get('vendas_ano_valor', 0):.2f}"],
    ]
    story.append(_criar_tabela_padrao(dados, [200, 312]))


def _adicionar_secao_devendo(story, contexto_dados, loja_usuario, titulo_style):
    story.append(Paragraph("<b>Relatório de Clientes Devendo (Fiado)</b>", titulo_style))
    story.append(Spacer(1, 10))
    dados = [["Cliente", "Valor Devido"]]
    for cliente in contexto_dados.get('clientes_devendo', []):
        if loja_usuario and cliente.loja != loja_usuario:
            continue
        dados.append([cliente.nome, f"R$ {cliente.saldo_geral:.2f}"])
    story.append(_criar_tabela_padrao(dados, [300, 212]))


def _adicionar_secao_credito(story, contexto_dados, loja_usuario, titulo_style):
    story.append(Paragraph("<b>Relatório de Clientes com Crédito</b>", titulo_style))
    story.append(Spacer(1, 10))
    dados = [["Cliente", "Crédito Disponível"]]
    for cliente in contexto_dados.get('clientes_credito', []):
        if loja_usuario and cliente.loja != loja_usuario:
            continue
        dados.append([cliente.nome, f"R$ {abs(cliente.saldo_geral):.2f}"])
    story.append(_criar_tabela_padrao(dados, [300, 212]))


def _adicionar_secao_estoque(story, contexto_dados, loja_usuario, titulo_style):
    story.append(Paragraph("<b>Inventário de Estoque Completo</b>", titulo_style))
    story.append(Spacer(1, 10))
    dados_estoque = [["Produto", "Preço (R$)", "Qtd em Estoque"]]
    for prod in contexto_dados.get('estoque_ordenado', []):
        if loja_usuario and prod.loja != loja_usuario:
            continue
        dados_estoque.append([prod.nome, f"R$ {prod.preco_venda:.2f}", str(prod.quantidade_estoque)])
    story.append(_criar_tabela_padrao(dados_estoque, [250, 130, 132]))


def _preencher_aba_resumo(ws, contexto_dados):
    ws.title = "Resumo Executivo"
    ws.append(["Métrica", "Valor (R$)"])
    ws.append(["Faturamento Total", float(contexto_dados.get('total_geral_vendas', 0))])
    ws.append(["Ticket Médio", float(contexto_dados.get('ticket_medio', 0))])
    ws.append(["Total a Receber", float(contexto_dados.get('total_fiado_pendente', 0))])
    ws.append(["Crédito de Clientes", float(contexto_dados.get('total_credito_clientes', 0))])


def _preencher_aba_estoque(ws, contexto_dados, loja_usuario):
    ws.title = ABA_ESTOQUE
    ws.append(["Produto", "Preço de Venda", "Quantidade em Estoque"])
    for prod in contexto_dados.get('estoque_ordenado', []):
        if loja_usuario and prod.loja != loja_usuario:
            continue
        ws.append([prod.nome, float(prod.preco_venda), prod.quantidade_estoque])


def _preencher_aba_devendo(ws, contexto_dados, loja_usuario):
    ws.title = ABA_CLIENTES_DEVENDO
    ws.append(["Cliente", "Valor Devido"])
    for cliente in contexto_dados.get('clientes_devendo', []):
        if loja_usuario and cliente.loja != loja_usuario:
            continue
        ws.append([cliente.nome, float(cliente.saldo_geral)])


def _preencher_aba_credito(ws, contexto_dados, loja_usuario):
    ws.title = ABA_CREDITO
    ws.append(["Cliente", "Crédito Disponível"])
    for cliente in contexto_dados.get('clientes_credito', []):
        if loja_usuario and cliente.loja != loja_usuario:
            continue
        ws.append([cliente.nome, float(abs(cliente.saldo_geral))])


def gerar_relatorio_pdf_secao(tipo_secao, contexto_dados, caminho_arquivo, loja_usuario=None):
    loja_contexto = contexto_dados.get('loja') if isinstance(contexto_dados, dict) else getattr(contexto_dados, 'loja', None)
    
    if loja_usuario and loja_contexto and loja_contexto != loja_usuario:
        raise PermissionDenied("Acesso negado: Tentativa de exportar dados de outra loja.")

    doc = SimpleDocTemplate(caminho_arquivo, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1f2937'), spaceAfter=10)
    
    handlers = {
        'resumo': lambda: _adicionar_secao_resumo(story, contexto_dados, titulo_style),
        'geral': lambda: [
            _adicionar_secao_resumo(story, contexto_dados, titulo_style),
            _adicionar_secao_temporal(story, contexto_dados, titulo_style),
            _adicionar_secao_devendo(story, contexto_dados, loja_usuario, titulo_style),
            _adicionar_secao_credito(story, contexto_dados, loja_usuario, titulo_style),
            _adicionar_secao_estoque(story, contexto_dados, loja_usuario, titulo_style),
        ],
        'temporal': lambda: _adicionar_secao_temporal(story, contexto_dados, titulo_style),
        'devendo': lambda: _adicionar_secao_devendo(story, contexto_dados, loja_usuario, titulo_style),
        'credito': lambda: _adicionar_secao_credito(story, contexto_dados, loja_usuario, titulo_style),
        'estoque': lambda: _adicionar_secao_estoque(story, contexto_dados, loja_usuario, titulo_style),
    }

    if tipo_secao in handlers:
        handlers[tipo_secao]()

    doc.build(story)


def gerar_relatorio_excel_secao(tipo_secao, contexto_dados, caminho_arquivo, loja_usuario=None):
    wb = openpyxl.Workbook()
    ws = wb.active

    handlers = {
        'resumo': lambda: _preencher_aba_resumo(ws, contexto_dados),
        'estoque': lambda: _preencher_aba_estoque(ws, contexto_dados, loja_usuario),
        'devendo': lambda: _preencher_aba_devendo(ws, contexto_dados, loja_usuario),
        'credito': lambda: _preencher_aba_credito(ws, contexto_dados, loja_usuario),
        'geral': lambda: [
            _preencher_aba_resumo(ws, contexto_dados),
            _preencher_aba_estoque(wb.create_sheet(title=ABA_ESTOQUE), contexto_dados, loja_usuario),
            _preencher_aba_devendo(wb.create_sheet(title=ABA_CLIENTES_DEVENDO), contexto_dados, loja_usuario),
        ]
    }

    if tipo_secao in handlers:
        handlers[tipo_secao]()
    else:
        # Fallback padrão
        _preencher_aba_resumo(ws, contexto_dados)
        _preencher_aba_estoque(wb.create_sheet(title=ABA_ESTOQUE), contexto_dados, loja_usuario)
        _preencher_aba_devendo(wb.create_sheet(title=ABA_CLIENTES_DEVENDO), contexto_dados, loja_usuario)

    wb.save(caminho_arquivo)


gerar_relatorio_pdf = gerar_relatorio_pdf_secao
gerar_relatorio_excel = gerar_relatorio_excel_secao
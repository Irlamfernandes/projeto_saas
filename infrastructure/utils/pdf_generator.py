from xml.sax.saxutils import escape
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from infrastructure.utils.formatacao import reais
from infrastructure.utils.pdf_marca import cabecalho_da_loja

QUANTIDADE_DE_COMPRAS_NO_EXTRATO = 5

COR_DEVENDO = colors.HexColor('#dc2626')
COR_CREDITO = colors.HexColor('#16a34a')
COR_NEUTRA = colors.HexColor('#4b5563')

ESTILO_TABELA = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 1), (-1, -1), 8.5),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
])


def gerar_extrato_pdf_cliente(cliente, caminho_arquivo, loja_usuario=None, storage=None):
    if loja_usuario and cliente.loja != loja_usuario:
        raise PermissionDenied("Acesso negado: Este cliente pertence a outra loja.")

    estilos = getSampleStyleSheet()
    texto_situacao, cor_situacao = situacao_financeira(cliente.saldo_geral)

    story = [
        *cabecalho_da_loja(cliente.loja, "Extrato Oficial de Conta / Caderneta", storage),
        Paragraph(f"<b>Cliente:</b> {escape(cliente.nome)}", estilos['Normal']),
        Paragraph(f"<b>Telefone:</b> {escape(cliente.telefone or 'Não informado')}", estilos['Normal']),
        Spacer(1, 10),
        Paragraph(texto_situacao, _estilo(estilos['Normal'], fontSize=11, textColor=cor_situacao, spaceAfter=15, fontName='Helvetica-Bold')),
        Spacer(1, 5),
        Paragraph(f"<b>Últimas {QUANTIDADE_DE_COMPRAS_NO_EXTRATO} Compras Registradas no Sistema:</b>", estilos['Heading3']),
        Spacer(1, 5),
        _tabela_de_compras(cliente),
    ]

    documento = SimpleDocTemplate(
        caminho_arquivo, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30,
    )
    documento.build(story)


def situacao_financeira(saldo):
    """Texto e cor do resumo: positivo = devendo, negativo = crédito."""
    if saldo > 0:
        return f"Situação: DEVENDO {reais(saldo)} (Valor Pendente)", COR_DEVENDO
    if saldo < 0:
        return f"Situação: CRÉDITO DE {reais(abs(saldo))} (Valor a mais)", COR_CREDITO
    return "Situação: TUDO CERTO (Conta Quitado / Sem Saldo Pendente)", COR_NEUTRA


def linhas_de_compras(cliente):
    vendas = (
        cliente.vendas.prefetch_related('itens__produto', 'parcelas')
        .order_by('-data_venda')[:QUANTIDADE_DE_COMPRAS_NO_EXTRATO]
    )
    linhas = [
        [
            timezone.localtime(venda.data_venda).strftime('%d/%m/%Y %H:%M'),
            ", ".join(f"{item.quantidade}x {item.produto.nome}" for item in venda.itens.all())
            + "".join(f" · vence {parcela.vencimento:%d/%m/%Y}" for parcela in venda.parcelas.all()),
            reais(venda.valor_total),
        ]
        for venda in vendas
    ]
    return linhas or [["-", "Nenhuma compra registrada", "-"]]


def _tabela_de_compras(cliente):
    tabela = Table([["Data", "Descrição dos Produtos", "Total (R$)"], *linhas_de_compras(cliente)], colWidths=[100, 320, 115])
    tabela.setStyle(ESTILO_TABELA)
    return tabela


def _estilo(base, **atributos):
    return ParagraphStyle(f"{base.name}-extrato", parent=base, **atributos)

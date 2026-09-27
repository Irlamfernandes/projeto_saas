"""Botão "?" do topo de cada tela: escolhe o texto de ajuda pela rota atual."""
from django import template
from interfaces.desenvolvedor import CORSARIOS_CODE

register = template.Library()

# Rota -> arquivo em interfaces/templates/interfaces/ajuda/. Tela sem ajuda aqui não mostra o botão.
AJUDA_POR_ROTA = {
    'dashboard': 'inicio',
    'vendas': 'vendas',
    'venda_editar': 'venda_editar',
    'produtos': 'produtos',
    'editar_produto': 'produto_editar',
    'clientes': 'clientes',
    'extrato_cliente': 'caderneta',
    'relatorios': 'relatorios',
    'relatorios_vendas': 'relatorios_vendas',
    'relatorios_produtos': 'relatorios_produtos',
    'relatorios_clientes': 'relatorios_clientes',
    'relatorios_alteracoes': 'relatorios_alteracoes',
    'gastos': 'gastos',
    'configuracoes': 'configuracoes',
    'planos': 'planos',
    'cobranca': 'cobranca',
}


@register.simple_tag(takes_context=True)
def ajuda_da_tela(context):
    """Caminho do texto de ajuda da tela atual; vazio se a tela não tiver."""
    rota = getattr(context.get('request'), 'resolver_match', None)
    nome = AJUDA_POR_ROTA.get(rota.url_name) if rota else None
    return f'interfaces/ajuda/{nome}.html' if nome else ''


@register.simple_tag(takes_context=True)
def link_suporte(context):
    """WhatsApp de suporte já dizendo de qual loja é o pedido."""
    usuario = getattr(context.get('request'), 'user', None)
    loja = getattr(usuario, 'loja', None)
    return CORSARIOS_CODE.link_suporte(loja.nome_loja if loja else 'Painel global')

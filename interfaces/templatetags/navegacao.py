from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_ativo(context, *nomes_de_rota):
    """'page' quando a rota atual é uma das informadas (separadas por espaço ou em argumentos) (para aria-current); vazio caso contrário."""
    rota = getattr(context.get('request'), 'resolver_match', None)
    nomes = ' '.join(nomes_de_rota).split()  # aceita 'a b' ou 'a', 'b'
    return 'page' if rota and rota.url_name in nomes else ''


@register.filter
def iniciais(nome):
    """Até duas iniciais maiúsculas: 'Padaria Pão de Mel' -> 'PP'."""
    palavras = [p for p in str(nome or '').split() if p[:1].isalnum()]
    return ''.join(p[0] for p in palavras[:2]).upper() or '?'

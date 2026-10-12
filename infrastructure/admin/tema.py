"""Menu lateral e favicon do admin (tema django-unfold). Ícones: nomes do Material Symbols."""
from django.templatetags.static import static
from django.urls import reverse_lazy


def menu_lateral(_request):
    """Unfold chama com o request; o menu é igual para todos (cada item confere a permissão)."""
    return [
        {'items': [_item('Painel', 'dashboard', 'admin:index')]},
        {'title': 'Lojas', 'items': [
            _item('Lojas', 'storefront', 'admin:infrastructure_lojamodel_changelist', 'view_lojamodel'),
            _item('Usuários', 'group', 'admin:infrastructure_usuariomodel_changelist', 'view_usuariomodel'),
        ]},
        {'title': 'Assinaturas', 'items': [
            _item('Planos', 'sell', 'admin:infrastructure_plano_changelist', 'view_plano'),
            _item('Cobranças', 'receipt_long', 'admin:infrastructure_cobranca_changelist', 'view_cobranca'),
        ]},
        {'title': 'Auditoria', 'items': [
            _item('Histórico de alterações', 'history', 'admin:infrastructure_registrodealteracao_changelist',
                  'view_registrodealteracao'),
        ]},
        {'title': 'Sistema', 'items': [
            _item('Erros do sistema', 'bug_report', 'admin:infrastructure_errodosistema_changelist', 'view_errodosistema'),
            _item('Backups', 'backup', 'admin:infrastructure_backup_changelist', 'view_backup'),
            _item('Tentativas de login', 'lock_person', 'admin:infrastructure_tentativasdelogin_changelist',
                  'view_tentativasdelogin'),
        ]},
    ]


def favicons(_request):
    return [
        {'rel': 'icon', 'type': 'image/svg+xml', 'href': static('images/logo.svg')},
        {'rel': 'icon', 'type': 'image/png', 'href': static('images/icon-192.png')},
    ]


def _item(titulo, icone, rota, permissao=None):
    item = {'title': titulo, 'icon': icone, 'link': reverse_lazy(rota)}
    if permissao:
        item['permission'] = lambda request: request.user.has_perm(f'infrastructure.{permissao}')
    return item

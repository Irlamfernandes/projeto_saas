from .loja_admin import LojaAdmin
from .usuario_admin import CustomUserAdmin
from .registro_de_alteracao_admin import RegistroDeAlteracaoAdmin
from .assinatura_admin import CobrancaAdmin, PlanoAdmin

from django.contrib import admin

# Painel com números e gráficos (infrastructure/admin/painel.py) no lugar da lista de apps.
admin.site.index_template = 'admin/painel.html'
admin.site.index_title = 'Painel'

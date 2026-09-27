from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView
from interfaces.views import (
    extrato_pdf_view, login_view, dashboard_view, alterar_senha_view, produtos_view, 
    produto_editar_view, clientes_view, cliente_editar_view, vendas_view, 
    extrato_cliente_view, venda_editar_view, relatorio_view, exportar_excel_modular_view,
    exportar_pdf_modular_view, relatorios_vendas_view, relatorios_produtos_view, relatorios_clientes_view,
    relatorios_alteracoes_view, venda_cancelar_view, configuracoes_view, marca_enviar_view, marca_remover_view,
    planos_view, cobranca_view, cobranca_situacao_view,
)

urlpatterns = [
    path('', lambda request: redirect('login', permanent=False)),
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    path('dashboard/', dashboard_view, name='dashboard'),
    path('alterar-senha/', alterar_senha_view, name='alterar_senha'),

    path('dashboard/produtos/', produtos_view, name='produtos'),
    path('produtos/editar/<int:pk>/', produto_editar_view, name='editar_produto'),

    path('dashboard/clientes/', clientes_view, name='clientes'),
    path('clientes/editar/<int:pk>/', cliente_editar_view, name='editar_cliente'),

    path('dashboard/vendas/', vendas_view, name='vendas'),
    path('clientes/<int:cliente_id>/extrato/', extrato_cliente_view, name='extrato_cliente'),
    path('clientes/<int:cliente_id>/pdf/', extrato_pdf_view, name='extrato_pdf'),
    path('vendas/<int:venda_id>/editar/', venda_editar_view, name='venda_editar'),
    path('vendas/<int:venda_id>/cancelar/', venda_cancelar_view, name='venda_cancelar'),

    path('configuracoes/', configuracoes_view, name='configuracoes'),
    path('configuracoes/marca/', marca_enviar_view, name='marca_enviar'),
    path('configuracoes/marca/remover/', marca_remover_view, name='marca_remover'),
    path('configuracoes/planos/', planos_view, name='planos'),
    path('configuracoes/planos/cobranca/<int:pk>/', cobranca_view, name='cobranca'),
    path('configuracoes/planos/cobranca/<int:pk>/situacao/', cobranca_situacao_view, name='cobranca_situacao'),

    path('relatorios/', relatorio_view, name='relatorios'),
    path('relatorios/vendas/', relatorios_vendas_view, name='relatorios_vendas'),
    path('relatorios/produtos/', relatorios_produtos_view, name='relatorios_produtos'),
    path('relatorios/clientes/', relatorios_clientes_view, name='relatorios_clientes'),
    path('relatorios/alteracoes/', relatorios_alteracoes_view, name='relatorios_alteracoes'),
    path('relatorios/exportar/pdf/<str:tipo>/', exportar_pdf_modular_view, name='exportar_pdf_modular'),
    path('relatorios/exportar/excel/<str:tipo>/', exportar_excel_modular_view, name='exportar_excel_modular'),
]
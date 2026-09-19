from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView
from interfaces.views import (
    conta_view, extrato_pdf_view, login_view, dashboard_view, alterar_senha_view, produtos_view, 
    produto_editar_view, clientes_view, cliente_editar_view, vendas_view, 
    extrato_cliente_view, venda_editar_view, relatorio_view, exportar_excel_modular_view,
    exportar_pdf_modular_view, assinatura_view
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

    path('relatorios/', relatorio_view, name='relatorios'),
    path('relatorios/exportar/pdf/<str:tipo>/', exportar_pdf_modular_view, name='exportar_pdf_modular'),
    path('relatorios/exportar/excel/<str:tipo>/', exportar_excel_modular_view, name='exportar_excel_modular'),

    path('conta/', conta_view, name='conta'),
    
    path('loja/<uuid:loja_id>/assinatura/', assinatura_view, name='assinatura'),
]
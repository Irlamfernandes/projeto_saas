from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView
from interfaces.views import (
    login_view, dashboard_view, alterar_senha_view, produtos_view, 
    produto_editar_view, clientes_view, cliente_editar_view
)
urlpatterns = [
    path('', lambda request: redirect('login', permanent=False)),
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('alterar-senha/', alterar_senha_view, name='alterar_senha'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    path('dashboard/produtos/', produtos_view, name='produtos'),
    path('produtos/editar/<int:pk>/', produto_editar_view, name='editar_produto'),

    path('dashboard/clientes/', clientes_view, name='clientes'),
    path('clientes/editar/<int:pk>/', cliente_editar_view, name='editar_cliente'),
]
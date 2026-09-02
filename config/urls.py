from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView
from interfaces.views import login_view, dashboard_view, alterar_senha_view

urlpatterns = [
    path('', lambda request: redirect('login', permanent=False)), # Redireciona a raiz para o login
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('alterar-senha/', alterar_senha_view, name='alterar_senha'), # <-- ADICIONE ESTA LINHA
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]
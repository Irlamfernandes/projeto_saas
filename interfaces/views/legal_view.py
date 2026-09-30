"""Termos de uso e política de privacidade: abertos a qualquer pessoa, sem login."""
from django.shortcuts import render


def termos_view(request):
    return render(request, 'interfaces/legal/termos.html')


def privacidade_view(request):
    return render(request, 'interfaces/legal/privacidade.html')

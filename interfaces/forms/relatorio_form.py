from datetime import timedelta
from django import forms
from application.relatorios.periodos import hoje_local
from application.relatorios.painel import LIMITE_ESTOQUE_BAIXO_PADRAO


class PeriodoForm(forms.Form):
    data_inicio = forms.DateField(required=False)
    data_fim = forms.DateField(required=False)

    def intervalo(self):
        """(início, fim); datas ausentes ou malformadas são ignoradas, como sempre foi na tela."""
        self.is_valid()
        return self.cleaned_data.get('data_inicio'), self.cleaned_data.get('data_fim')

    def intervalo_ou_ultimos(self, dias=30, agora=None):
        """Como `intervalo()`, mas sem nenhuma data informada usa os últimos `dias` dias (até hoje)."""
        inicio, fim = self.intervalo()
        if inicio or fim:
            return inicio, fim
        hoje = hoje_local(agora)
        return hoje - timedelta(days=dias - 1), hoje


class LimiteEstoqueForm(forms.Form):
    limite_estoque = forms.IntegerField(required=False, min_value=0, max_value=100_000)

    def limite(self):
        if not self.is_valid() or self.cleaned_data['limite_estoque'] is None:
            return LIMITE_ESTOQUE_BAIXO_PADRAO
        return self.cleaned_data['limite_estoque']


def escolher_dias(valor, opcoes, padrao):
    """Número de dias vindo da URL, restrito às `opcoes` oferecidas na tela."""
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return padrao
    return dias if dias in opcoes else padrao

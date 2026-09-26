from django import forms
from application.relatorios.selectors import LIMITE_ESTOQUE_BAIXO_PADRAO


class PeriodoForm(forms.Form):
    data_inicio = forms.DateField(required=False)
    data_fim = forms.DateField(required=False)

    def intervalo(self):
        """(início, fim); datas ausentes ou malformadas são ignoradas, como sempre foi na tela."""
        self.is_valid()
        return self.cleaned_data.get('data_inicio'), self.cleaned_data.get('data_fim')


class LimiteEstoqueForm(forms.Form):
    limite_estoque = forms.IntegerField(required=False, min_value=0, max_value=100_000)

    def limite(self):
        if not self.is_valid() or self.cleaned_data['limite_estoque'] is None:
            return LIMITE_ESTOQUE_BAIXO_PADRAO
        return self.cleaned_data['limite_estoque']

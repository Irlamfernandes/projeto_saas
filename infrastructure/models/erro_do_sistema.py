from django.conf import settings
from django.db import models
from django.utils import timezone
from infrastructure.models.loja_model import LojaModel


class ErroDoSistema(models.Model):
    """Erro inesperado em produção (tela "Erros do sistema" do admin).

    O mesmo erro (mesmo tipo, no mesmo ponto do código) soma em `ocorrencias` em vez de criar linhas novas.
    Depois de marcado como resolvido, se voltar a acontecer, abre um registro novo.
    """
    assinatura = models.CharField(max_length=64, db_index=True)
    tipo = models.CharField(max_length=200)
    mensagem = models.TextField(blank=True)
    local = models.CharField(max_length=300, blank=True, help_text="Arquivo, linha e função onde o erro aconteceu.")
    caminho = models.CharField(max_length=500, blank=True, help_text="Endereço da tela (sem os parâmetros).")
    metodo = models.CharField(max_length=10, blank=True)
    loja = models.ForeignKey(LojaModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    detalhes = models.TextField(blank=True, help_text="Caminho do erro pelo código (traceback).")
    ocorrencias = models.PositiveIntegerField(default=1)
    primeira_vez = models.DateTimeField(default=timezone.now)
    ultima_vez = models.DateTimeField(default=timezone.now, db_index=True)
    resolvido = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'erros_do_sistema'
        verbose_name = 'Erro do sistema'
        verbose_name_plural = 'Erros do sistema'
        ordering = ['resolvido', '-ultima_vez']

    def __str__(self):
        return f"{self.tipo} · {self.local or self.caminho}"

import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone

DIAS_DE_TESTE_GRATIS = 30


def vencimento_do_teste_gratis():
    """Vencimento de uma loja nova: hoje + 30 dias grátis."""
    return timezone.localdate() + timedelta(days=DIAS_DE_TESTE_GRATIS)


class LojaModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_loja = models.CharField(max_length=150, db_index=True)
    ativo = models.BooleanField(default=True, help_text="Desmarque para colocar a loja fora do ar.")
    # Marca (logotipo) no Storage: aparece no topo do sistema e nos PDFs.
    logo_url = models.URLField(max_length=500, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    # Até quando a loja pode usar o sistema por completo. Só muda com pagamento confirmado (ou pelo admin).
    vencimento = models.DateField(default=vencimento_do_teste_gratis)
    # E-mail para o comprovante do Pix, guardado exatamente como a loja digitou.
    email_cobranca = models.CharField(max_length=254, blank=True, default='')

    def __str__(self):
        return self.nome_loja

    class Meta:
        db_table = 'lojas'
        verbose_name = 'Loja'
        verbose_name_plural = 'Lojas'

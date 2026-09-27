import uuid
from django.conf import settings
from django.db import models

class LojaModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_loja = models.CharField(max_length=150, db_index=True)
    ativo = models.BooleanField(default=True, help_text="Desmarque para colocar a loja fora do ar.")
    # Marca (logotipo) no Storage: aparece no topo do sistema e nos PDFs.
    logo_url = models.URLField(max_length=500, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome_loja

    class Meta:
        db_table = 'lojas'
        verbose_name = 'Loja'
        verbose_name_plural = 'Lojas'
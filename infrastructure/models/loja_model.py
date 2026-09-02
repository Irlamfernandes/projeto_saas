from django.db import models

class LojaModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome_loja = models.CharField(max_length=150)
    ativo = models.BooleanField(default=True, help_text="Desmarque para colocar a loja fora do ar.")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome_loja

    class Meta:
        db_table = 'lojas'
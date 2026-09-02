from django.contrib.auth.models import AbstractUser
from django.db import models
from infrastructure.models.loja_model import LojaModel

class UsuarioModel(AbstractUser):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='usuarios', null=True, blank=True)
    deve_trocar_senha = models.BooleanField(default=True, help_text="Indica se o usuário deve trocar a senha no próximo login.")

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return f"{self.username} ({self.loja.nome_loja if self.loja else 'Admin'})"
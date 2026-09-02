from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from infrastructure.models.loja_model import LojaModel

class CustomUsernameValidator(UnicodeUsernameValidator):
    regex = r'^[\w.@+\- ]+$'
    message = (
        'Insira um nome válido. O nome pode conter letras, números, '
        'espaços e os caracteres @/./+/-/_.'
    )

class UsuarioModel(AbstractUser):
    username_validator = CustomUsernameValidator()

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text='Obrigatório. 150 caracteres ou menos. Letras, números e espaços.',
        validators=[username_validator],
        error_messages={
            'unique': "Já existe um usuário com este nome.",
        },
    )
    
    loja = models.ForeignKey(
        LojaModel, 
        on_delete=models.CASCADE, 
        related_name='usuarios', 
        null=True, 
        blank=True,
        db_index=True
    )
    deve_trocar_senha = models.BooleanField(
        default=True, 
        help_text="Indica se o usuário deve trocar a senha no próximo login."
    )

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def clean(self):
        super().clean()
        if not self.is_superuser and not self.is_staff and not self.loja:
            raise ValidationError({
                'loja': 'Usuários comuns do sistema devem estar obrigatoriamente associados a uma loja.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        loja_nome = self.loja.nome_loja if self.loja else 'Admin Global'
        return f"{self.username} ({loja_nome})"
from django.contrib import admin
from infrastructure.models.loja_model import LojaModel

@admin.register(LojaModel)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_loja') # Removi o campo de data ou use o nome real se houver
    search_fields = ('nome_loja',)

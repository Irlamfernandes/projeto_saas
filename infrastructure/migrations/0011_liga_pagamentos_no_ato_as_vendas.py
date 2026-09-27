"""Liga à venda os pagamentos feitos no ato, que até aqui só eram identificados pelo texto da observação.

Só liga quando pagamento e venda são do mesmo cliente e da mesma loja. Pagamentos que ficaram com outro
cliente (a venda mudou de cliente antes desta correção) não são alterados: dinheiro não se move sozinho.
"""
import re
from django.db import migrations

OBSERVACAO = re.compile(r'^Pagamento no ato da Venda #(\d+)$')


def ligar(apps, schema_editor):
    PagamentoCliente = apps.get_model('infrastructure', 'PagamentoCliente')
    Venda = apps.get_model('infrastructure', 'Venda')
    pagamentos = PagamentoCliente.objects.filter(venda__isnull=True, observacao__startswith='Pagamento no ato da Venda #')
    for pagamento in pagamentos.iterator():
        encontrado = OBSERVACAO.match(pagamento.observacao)
        if not encontrado:
            continue
        venda = Venda.objects.filter(
            pk=int(encontrado.group(1)), loja_id=pagamento.loja_id, cliente_id=pagamento.cliente_id,
        ).first()
        if venda:
            PagamentoCliente.objects.filter(pk=pagamento.pk).update(venda=venda)


class Migration(migrations.Migration):

    dependencies = [
        ('infrastructure', '0010_formas_de_pagamento_e_registro_de_alteracoes'),
    ]

    operations = [
        migrations.RunPython(ligar, migrations.RunPython.noop),
    ]

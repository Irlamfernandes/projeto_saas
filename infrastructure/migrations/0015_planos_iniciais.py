from decimal import Decimal
from django.db import migrations

# Preços de teste (R$ 0,01). Para cobrar de verdade, altere os preços no admin (Planos).
PLANOS = [
    ('30 dias', 30, 'dias', 1),
    ('90 dias', 90, 'dias', 2),
    ('6 meses', 6, 'meses', 3),
    ('12 meses', 12, 'meses', 4),
]


def criar_planos(apps, schema_editor):
    Plano = apps.get_model('infrastructure', 'Plano')
    for nome, quantidade, unidade, ordem in PLANOS:
        Plano.objects.get_or_create(
            nome=nome, defaults={'quantidade': quantidade, 'unidade': unidade, 'ordem': ordem, 'preco': Decimal('0.01')},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('infrastructure', '0014_planos_e_cobrancas'),
    ]

    operations = [
        migrations.RunPython(criar_planos, migrations.RunPython.noop),
    ]

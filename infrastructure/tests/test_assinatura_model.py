from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from infrastructure.models import Cobranca, LojaModel, Plano


class AssinaturaModelTest(TestCase):

    def test_textos_no_admin(self):
        plano = Plano.objects.get(nome="30 dias")
        cobranca = Cobranca.objects.create(
            loja=LojaModel.objects.create(nome_loja="Padaria"), plano=plano, plano_nome=plano.nome,
            quantidade=30, unidade='dias', valor=Decimal('0.01'), email_pagador='a@b.com',
            expira_em=timezone.now() + timedelta(minutes=30),
        )
        self.assertEqual(str(plano), "30 dias")
        self.assertEqual(str(cobranca), "30 dias · Padaria · Aguardando pagamento")

    def test_cada_cobranca_tem_referencia_unica(self):
        plano = Plano.objects.get(nome="30 dias")
        loja = LojaModel.objects.create(nome_loja="Padaria")
        dados = dict(loja=loja, plano=plano, plano_nome='x', quantidade=1, unidade='dias', valor=1, email_pagador='a@b.com',
                     expira_em=timezone.now())
        self.assertNotEqual(Cobranca.objects.create(**dados).referencia, Cobranca.objects.create(**dados).referencia)

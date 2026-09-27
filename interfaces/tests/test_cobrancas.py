from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import unquote
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from application.a_receber.selectors import clientes_a_cobrar
from infrastructure.models import (
    Cliente, ItemVenda, LembreteDePagamento, LojaModel, Parcela, Produto, RegistroDeAlteracao, Venda,
)
from interfaces.cobrancas import cobrancas_na_tela, link_do_whatsapp, mensagem_de_cobranca, numero_do_whatsapp

User = get_user_model()
HOJE = timezone.localdate()


class NumeroDoWhatsappTest(SimpleTestCase):

    def test_formatos_de_telefone(self):
        casos = {
            '(24) 99999-0000': '5524999990000',
            '24 3333-4444': '552433334444',
            '+55 24 99999-0000': '5524999990000',
            '5524999990000': '5524999990000',
            '99999-0000': '',
            '': '',
            None: '',
            '4499999990000': '',
        }
        for telefone, esperado in casos.items():
            with self.subTest(telefone=telefone):
                self.assertEqual(numero_do_whatsapp(telefone), esperado)

    def test_link_leva_o_texto_codificado(self):
        self.assertEqual(link_do_whatsapp('24999990000', 'Olá & até\nlogo'),
                         'https://wa.me/5524999990000?text=Ol%C3%A1%20%26%20at%C3%A9%0Alogo')
        self.assertEqual(link_do_whatsapp('123', 'oi'), '')


class CobrancasTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Doces da Ana", ativo=True)
        self.usuario = User.objects.create_user(username="caixa", password="x", loja=self.loja, deve_trocar_senha=False)
        self.maria = Cliente.objects.create(loja=self.loja, nome="Maria", telefone="(24) 99999-0000")
        self.bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('12.00'))

    def venda(self, cliente, quantidade, vencimento, quando):
        venda = Venda.objects.create(loja=self.loja, cliente=cliente, valor_total=Decimal('12.00') * quantidade,
                                     data_venda=quando)
        ItemVenda.objects.create(venda=venda, produto=self.bolo, quantidade=quantidade, preco_unitario=Decimal('12.00'))
        Parcela.objects.create(venda=venda, vencimento=vencimento)
        return venda


class MensagemDeCobrancaTest(CobrancasTestCase):

    def test_lista_cada_compra_com_data_itens_vencimento_e_valor(self):
        agora = timezone.now()
        self.venda(self.maria, 2, HOJE - timedelta(days=3), agora - timedelta(days=10))
        self.venda(self.maria, 1, HOJE, agora - timedelta(days=5))
        self.venda(self.maria, 3, HOJE + timedelta(days=4), agora - timedelta(days=1))
        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)

        def dia(dias):
            return f"{HOJE + timedelta(days=dias):%d/%m}"

        def compra(dias_atras):
            return f"{timezone.localtime(agora - timedelta(days=dias_atras)):%d/%m}"

        self.assertEqual(mensagem_de_cobranca(cobranca), "\n".join([
            "Olá, Maria! Aqui é da Doces da Ana.",
            "Passando para lembrar do pagamento combinado:",
            "",
            f"• Compra de {compra(10)} (2× Bolo): venceu em {dia(-3)} · R$ 24,00",
            f"• Compra de {compra(5)} (1× Bolo): vence hoje · R$ 12,00",
            f"• Compra de {compra(1)} (3× Bolo): vence em {dia(4)} · R$ 36,00",
            "",
            "Total: R$ 72,00",
            "Se já pagou, pode desconsiderar esta mensagem. Obrigado!",
        ]))

    def test_parcelas_aparecem_numeradas(self):
        venda = self.venda(self.maria, 3, HOJE, timezone.now())
        Parcela.objects.create(venda=venda, vencimento=HOJE + timedelta(days=30))
        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)
        self.assertIn("(3× Bolo) parcela 1/2: vence hoje · R$ 18,00", mensagem_de_cobranca(cobranca))

    def test_item_com_opcoes_mostra_a_escolha(self):
        venda = self.venda(self.maria, 1, HOJE, timezone.now())
        venda.itens.update(opcoes=[{'nome': 'Sabor', 'valor': 'Chocolate'}])
        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)
        self.assertIn("(1× Bolo (Chocolate))", mensagem_de_cobranca(cobranca))

    def test_data_da_compra_no_fuso_local(self):
        meia_noite_utc = timezone.make_aware(datetime(2026, 1, 10, 1, 0), timezone.get_fixed_timezone(0))
        self.venda(self.maria, 1, HOJE, meia_noite_utc)
        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)
        self.assertIn("Compra de 09/01", mensagem_de_cobranca(cobranca))

    def test_na_tela_vem_com_o_link_e_sem_telefone_fica_sem_link(self):
        sem_telefone = Cliente.objects.create(loja=self.loja, nome="Zeca")
        self.venda(self.maria, 1, HOJE, timezone.now())
        self.venda(sem_telefone, 1, HOJE, timezone.now())

        telas = {tela.cobranca.cliente.nome: tela for tela in cobrancas_na_tela(clientes_a_cobrar(self.usuario, HOJE))}

        self.assertTrue(telas["Maria"].link.startswith("https://wa.me/5524999990000?text="))
        self.assertEqual(unquote(telas["Maria"].link.split("text=")[1]), telas["Maria"].mensagem)
        self.assertEqual(telas["Zeca"].link, "")


class CartaoDeCobrancasTest(CobrancasTestCase):

    def test_inicio_mostra_quem_cobrar_com_o_botao_do_whatsapp(self):
        self.venda(self.maria, 2, HOJE - timedelta(days=1), timezone.now())
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'data-cobrancas')
        self.assertContains(response, 'data-cobrar-todos')
        self.assertContains(response, f"Atrasado desde {HOJE - timedelta(days=1):%d/%m}")
        self.assertContains(response, 'href="https://wa.me/5524999990000?text=')
        self.assertContains(response, reverse('lembrete_de_pagamento', args=[self.maria.pk]))
        self.assertContains(response, 'id="cobrar-todos"')
        self.assertContains(response, 'js/cobrancas.js')

    def test_situacoes_lembrado_e_sem_telefone(self):
        zeca = Cliente.objects.create(loja=self.loja, nome="Zeca")
        self.venda(self.maria, 1, HOJE, timezone.now())
        self.venda(zeca, 1, HOJE + timedelta(days=3), timezone.now())
        LembreteDePagamento.objects.create(loja=self.loja, cliente=self.maria, valor=Decimal('12'))
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, "Vence hoje")
        self.assertContains(response, f"Vence {HOJE + timedelta(days=3):%d/%m}")
        self.assertContains(response, " data-lembrado>")
        self.assertContains(response, 'class="pilula-bom" data-selo-lembrado')
        self.assertContains(response, "Sem telefone")

    def test_sem_nada_para_cobrar(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, "Nada para cobrar")
        self.assertNotContains(response, 'id="cobrar-todos"')


class LembreteViewTest(CobrancasTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('lembrete_de_pagamento', args=[self.maria.pk])

    def test_anota_o_lembrete_com_o_valor_que_esta_vencendo(self):
        self.venda(self.maria, 2, HOJE, timezone.now())
        self.client.force_login(self.usuario)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 204)
        lembrete = LembreteDePagamento.objects.get()
        self.assertEqual((lembrete.cliente, lembrete.usuario, lembrete.valor), (self.maria, self.usuario, Decimal('24.00')))
        self.assertTrue(RegistroDeAlteracao.objects.filter(descricao="Maria · R$ 24,00").exists())

    def test_sem_nada_vencendo_nao_anota(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(self.url).status_code, 204)
        self.assertFalse(LembreteDePagamento.objects.exists())

    def test_so_aceita_post_e_cliente_da_propria_loja(self):
        outra = LojaModel.objects.create(nome_loja="Outra", ativo=True)
        de_fora = Cliente.objects.create(loja=outra, nome="De fora")
        self.client.force_login(self.usuario)

        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(reverse('lembrete_de_pagamento', args=[de_fora.pk])).status_code, 404)

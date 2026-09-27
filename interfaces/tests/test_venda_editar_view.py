from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from application.vendas.services import registrar_venda
from infrastructure.models import Acao, Cliente, LojaModel, Parcela, Produto, RegistroDeAlteracao, Venda

User = get_user_model()


class VendaEditarViewTestCase(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)
        self.superuser = User.objects.create_superuser(deve_trocar_senha=False, username="admin", password="password")
        self.user_loja1 = User.objects.create_user(deve_trocar_senha=False, username="user_loja1", password="senha-certa", loja=self.loja1)
        self.user_loja2 = User.objects.create_user(deve_trocar_senha=False, username="user_loja2", password="password", loja=self.loja2)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(deve_trocar_senha=False, username="user_sem_loja", password="password", loja=None)

        self.cliente = Cliente.objects.create(loja=self.loja1, nome="Cliente Alpha")
        self.outro_cliente = Cliente.objects.create(loja=self.loja1, nome="Outro")
        self.arroz = Produto.objects.create(loja=self.loja1, nome="Arroz", codigo_interno="AR", preco_venda=Decimal('20.00'), quantidade_estoque=10)
        self.cafe = Produto.objects.create(loja=self.loja1, nome="Café", preco_venda=Decimal('5.00'), quantidade_estoque=0)
        self.venda = registrar_venda(cliente=self.cliente, itens=[(self.arroz.pk, 2)], valor_pago=Decimal('40'), forma_pagamento='pix')
        self.url = reverse('venda_editar', args=[self.venda.pk])

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class VendaEditarViewTest(VendaEditarViewTestCase):

    def _editar(self, itens, usuario=None, **campos):
        self.client.force_login(usuario or self.user_loja1)
        dados = {'cliente': self.cliente.pk, 'forma_pagamento': 'pix', **campos}
        dados['item_produto'] = [produto.pk for produto, _ in itens]
        dados['item_quantidade'] = [quantidade for _, quantidade in itens]
        return self.client.post(self.url, dados)

    def test_usuario_sem_loja_recebe_permission_denied(self):
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_usuario_de_loja_inativa_recebe_permission_denied(self):
        self.loja1.ativo = False
        self.loja1.save()
        self.client.force_login(self.user_loja1)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_nao_edita_venda_de_outra_loja(self):
        self.client.force_login(self.user_loja2)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_get_traz_os_itens_atuais_e_o_estoque_reservado_de_volta(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url)

        self.assertEqual(response.context['itens_iniciais'], [{'id': self.arroz.pk, 'quantidade': 2, 'preco': '20.00'}])
        arroz = next(p for p in response.context['catalogo'] if p['id'] == self.arroz.pk)
        self.assertEqual(arroz['estoque'], 10, "as 2 unidades desta venda voltam a ficar disponíveis para ela")
        self.assertEqual(response.context['pago_no_ato'], Decimal('40'))
        self.assertContains(response, 'id="modal-cancelar-venda"')

    def test_get_mostra_o_vencimento_atual_e_o_valor_pago_no_ato(self):
        Parcela.objects.create(venda=self.venda, vencimento=date(2026, 10, 15))
        Parcela.objects.create(venda=self.venda, vencimento=date(2026, 11, 15))
        self.client.force_login(self.user_loja1)

        response = self.client.get(self.url)

        self.assertEqual(response.context['vencimentos'], [date(2026, 10, 15), date(2026, 11, 15)])
        self.assertContains(response, 'data-vencimentos="2026-10-15 2026-11-15 "')
        self.assertContains(response, 'name="vencimento" value="2026-10-15"')
        self.assertContains(response, 'data-pagou-no-ato="40.00"')

    def test_salva_o_novo_vencimento(self):
        self._editar([(self.arroz, 3)], vencimento='2026-11-01')
        self.assertEqual(list(self.venda.parcelas.values_list('vencimento', flat=True)), [date(2026, 11, 1)])

    def test_salva_parcelas(self):
        self._editar([(self.arroz, 5)], vencimento=['2026-12-01', '2026-11-01'])
        self.assertEqual(list(self.venda.parcelas.values_list('vencimento', flat=True)), [date(2026, 11, 1), date(2026, 12, 1)])

    def test_salva_varios_itens(self):
        Produto.objects.filter(pk=self.cafe.pk).update(quantidade_estoque=5)
        response = self._editar([(self.arroz, 1), (self.cafe, 2)])

        self.assertRedirects(response, reverse('vendas'))
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.valor_total, Decimal('30.00'))
        self.assertEqual(RegistroDeAlteracao.objects.get(acao=Acao.VENDA_EDITADA).usuario, self.user_loja1)

    def test_trocar_cliente_leva_o_pagamento_junto(self):
        self._editar([(self.arroz, 2)], cliente=self.outro_cliente.pk)
        self.assertEqual(self.venda.pagamentos_no_ato.get().cliente, self.outro_cliente)

    def test_erro_volta_para_a_edicao_sem_alterar(self):
        response = self._editar([(self.cafe, 1)])

        self.assertRedirects(response, self.url)
        self.assertIn("Estoque insuficiente para 'Café'. Disponível: 0 un.", self._mensagens(response))
        self.assertEqual(self.venda.itens.get().produto, self.arroz)

    def test_superuser_nao_move_venda_para_cliente_de_outra_loja(self):
        de_fora = Cliente.objects.create(loja=self.loja2, nome="Cliente Beta")
        self._editar([(self.arroz, 2)], usuario=self.superuser, cliente=de_fora.pk)

        self.venda.refresh_from_db()
        self.assertEqual(self.venda.cliente, self.cliente)


class VendaCancelarViewTest(VendaEditarViewTestCase):

    def setUp(self):
        super().setUp()
        self.url_cancelar = reverse('venda_cancelar', args=[self.venda.pk])

    def _cancelar(self, usuario=None, **dados):
        self.client.force_login(usuario or self.user_loja1)
        return self.client.post(self.url_cancelar, {'senha': 'senha-certa', 'motivo': 'lançada em dobro', **dados})

    def test_com_a_senha_certa_cancela_e_volta_para_vendas(self):
        numero = self.venda.pk
        response = self._cancelar()

        self.assertRedirects(response, reverse('vendas'))
        self.assertIn(f"Venda #{numero} cancelada. O estoque foi devolvido.", self._mensagens(response))
        self.assertFalse(Venda.objects.exists())
        self.arroz.refresh_from_db()
        self.assertEqual(self.arroz.quantidade_estoque, 10)

    def test_senha_errada_nao_cancela(self):
        response = self._cancelar(senha='chute')

        self.assertRedirects(response, self.url)
        self.assertIn("Senha incorreta. A venda não foi cancelada.", self._mensagens(response))
        self.assertTrue(Venda.objects.exists())

    def test_sem_motivo_nao_cancela(self):
        response = self._cancelar(motivo='')
        self.assertIn("Conte o motivo do cancelamento.", self._mensagens(response))
        self.assertTrue(Venda.objects.exists())

    def test_so_aceita_post(self):
        self.client.force_login(self.user_loja1)
        self.assertEqual(self.client.get(self.url_cancelar).status_code, 405)

    def test_nao_cancela_venda_de_outra_loja(self):
        response = self._cancelar(usuario=self.user_loja2, senha='password')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Venda.objects.exists())

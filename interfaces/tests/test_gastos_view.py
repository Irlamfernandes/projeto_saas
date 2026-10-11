from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models import Compra, Despesa, LojaModel, Perda, Produto

User = get_user_model()


class GastosViewTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja", ativo=True)
        self.usuario = User.objects.create_user(username="u", password="x", loja=self.loja, deve_trocar_senha=False)
        self.bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('30'), preco_custo=Decimal('10'),
                                           quantidade_estoque=5)
        self.hoje = timezone.localdate()
        self.client.force_login(self.usuario)

    def mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def lancar(self, tipo, **dados):
        return self.client.post(reverse('registrar_gasto', args=[tipo]), {'data': f"{self.hoje:%Y-%m-%d}", **dados})

    def voltar(self, tipo):
        return f"{reverse('gastos')}?aba={tipo}&mes={self.hoje:%Y-%m}"


class TelaTest(GastosViewTestCase):

    def test_abre_na_aba_de_despesa_com_resultado_e_abas_de_relatorios(self):
        response = self.client.get(reverse('gastos'))

        self.assertEqual(response.context['aba'], 'despesa')
        self.assertContains(response, 'Lançar despesa')
        self.assertContains(response, 'id="t-resultado"')
        self.assertContains(response, 'aria-current="page">Gastos</a>')
        self.assertContains(response, 'datalist id="categorias-de-despesa"')

    def test_abas_de_compra_e_perda_e_aba_desconhecida(self):
        self.assertContains(self.client.get(reverse('gastos'), {'aba': 'compra'}), 'data-modelo-item-compra')
        self.assertContains(self.client.get(reverse('gastos'), {'aba': 'perda'}), 'Lançar perda')
        self.assertEqual(self.client.get(reverse('gastos'), {'aba': 'xyz'}).context['aba'], 'despesa')

    def test_lista_os_lancamentos_do_mes_com_a_lixeira(self):
        despesa = Despesa.objects.create(loja=self.loja, data=self.hoje, categoria="Aluguel", valor=Decimal('900'))
        response = self.client.get(reverse('gastos'))
        self.assertContains(response, 'Aluguel')
        self.assertContains(response, reverse('excluir_gasto', args=['despesa', despesa.pk]))

    def test_mostra_o_mes_escolhido(self):
        mes_passado = self.hoje.replace(day=1) - timedelta(days=1)
        despesa = Despesa.objects.create(loja=self.loja, data=mes_passado, categoria="Conserto", valor=Decimal('900'))
        response = self.client.get(reverse('gastos'), {'mes': f"{mes_passado:%Y-%m}"})
        self.assertEqual(response.context['mes'].chave, f"{mes_passado:%Y-%m}")
        self.assertEqual(list(response.context['despesas']), [despesa])
        self.assertEqual(list(self.client.get(reverse('gastos')).context['despesas']), [])

    def test_inicio_tem_o_atalho_e_o_resultado_do_mes(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Lançar gasto')
        self.assertContains(response, 'até agora</span>')  # o link é lido com todo o texto do cartão
        self.assertContains(response, 'Sobrou R$ 0,00')


class LancarTest(GastosViewTestCase):

    def test_despesa(self):
        response = self.lancar('despesa', categoria='Luz', valor='120,50')

        self.assertRedirects(response, self.voltar('despesa'), fetch_redirect_response=False)
        self.assertEqual(self.mensagens(response), ["Despesa lançada!"])
        self.assertEqual(Despesa.objects.get().valor, Decimal('120.50'))

    def test_compra(self):
        response = self.lancar('compra', item_produto=[self.bolo.pk], item_quantidade=['3'], item_custo=['12'],
                               atualizar_custo='1')

        self.assertEqual(self.mensagens(response), ["Compra lançada! O estoque foi atualizado."])
        self.bolo.refresh_from_db()
        self.assertEqual((self.bolo.quantidade_estoque, self.bolo.preco_custo), (Decimal('8'), Decimal('12.00')))

    def test_perda(self):
        response = self.lancar('perda', produto=self.bolo.pk, quantidade='2', motivo='Venceu')

        self.assertEqual(self.mensagens(response), ["Perda lançada. O estoque foi baixado."])
        self.assertEqual(Perda.objects.get().quantidade, Decimal('2'))

    def test_erro_volta_para_a_aba_sem_mes(self):
        response = self.lancar('despesa', categoria='', valor='10')
        self.assertRedirects(response, f"{reverse('gastos')}?aba=despesa", fetch_redirect_response=False)
        self.assertEqual(self.mensagens(response), ["Escolha ou escreva a categoria da despesa."])

    def test_tipo_desconhecido_e_so_post(self):
        self.assertEqual(self.lancar('outra').status_code, 404)
        self.assertEqual(self.client.get(reverse('registrar_gasto', args=['despesa'])).status_code, 405)

    def test_superusuario_sem_loja_nao_lanca(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="x", deve_trocar_senha=False))
        response = self.lancar('despesa', categoria='Luz', valor='1')
        self.assertEqual(self.mensagens(response), ["Entre com um usuário de loja para lançar gastos."])
        self.assertFalse(Despesa.objects.exists())


class ExcluirTest(GastosViewTestCase):

    def excluir(self, tipo, pk):
        return self.client.post(reverse('excluir_gasto', args=[tipo, pk]))

    def test_exclui_e_volta_para_o_mes_do_lancamento(self):
        despesa = Despesa.objects.create(loja=self.loja, data=self.hoje, categoria="Luz", valor=Decimal('1'))
        response = self.excluir('despesa', despesa.pk)
        self.assertRedirects(response, self.voltar('despesa'), fetch_redirect_response=False)
        self.assertEqual(self.mensagens(response), ["Despesa excluída."])
        self.assertFalse(Despesa.objects.exists())

    def test_regra_de_negocio_recusa_e_avisa(self):
        self.lancar('compra', item_produto=[self.bolo.pk], item_quantidade=['3'], item_custo=['12'])
        Produto.objects.filter(pk=self.bolo.pk).update(quantidade_estoque=0)
        compra = Compra.objects.get()

        response = self.excluir('compra', compra.pk)

        self.assertIn("Não dá para excluir", self.mensagens(response)[-1])
        self.assertTrue(Compra.objects.exists())

    def test_nao_exclui_de_outra_loja(self):
        outra = LojaModel.objects.create(nome_loja="Outra")
        despesa = Despesa.objects.create(loja=outra, data=self.hoje, categoria="Luz", valor=Decimal('1'))
        self.assertEqual(self.excluir('despesa', despesa.pk).status_code, 404)

    def test_plano_vencido_bloqueia_o_envio(self):
        with patch('interfaces.decorators.plano_vencido', return_value=True):
            self.lancar('despesa', categoria='Luz', valor='1')
        self.assertFalse(Despesa.objects.exists())

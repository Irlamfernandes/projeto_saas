from django.contrib.messages import get_messages
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.venda import Venda, PagamentoCliente
from interfaces.views.extrato_cliente_view import TEMPLATE_EXTRATO_CLIENTE  # Importa a constante da view

User = get_user_model()


class ExtratoClienteViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            deve_trocar_senha=False,
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            deve_trocar_senha=False,
            username="user_loja1", password="password", loja=self.loja1
        )
        
        # Cria usuário sem loja ignorando o full_clean para testar a exceção de permissão
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                deve_trocar_senha=False,
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente_loja1 = Cliente.objects.create(loja=self.loja1, nome="Cliente Loja 1")
        self.cliente_loja2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Loja 2")

        # Dados associados ao cliente da loja 1
        agora = timezone.now()
        self.venda_l1 = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente_loja1, valor_total=150.0, data_venda=agora
        )
        self.pagamento_l1 = PagamentoCliente.objects.create(
            loja=self.loja1, cliente=self.cliente_loja1, valor=50.0, data_pagamento=agora
        )

    def _get_url_extrato(self, cliente_id):
        return reverse('extrato_cliente', args=[cliente_id])

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar o extrato."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self._get_url_extrato(self.cliente_loja1.pk))
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_acessa_extrato_cliente_da_propria_loja(self):
        """Usuário comum visualiza o extrato e a timeline da sua própria loja com sucesso."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self._get_url_extrato(self.cliente_loja1.pk))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TEMPLATE_EXTRATO_CLIENTE)
        self.assertEqual(response.context['cliente'], self.cliente_loja1)
        self.assertEqual(len(response.context['timeline']), 2) # 1 venda + 1 pagamento

    def test_usuario_comum_nao_acessa_extrato_cliente_de_outra_loja(self):
        """Usuário comum recebe 404 ao tentar acessar extrato de cliente de outra loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self._get_url_extrato(self.cliente_loja2.pk))
        self.assertEqual(response.status_code, 404)

    def test_superuser_acessa_extrato_de_qualquer_loja(self):
        """Superusuário consegue acessar o extrato de clientes de qualquer loja."""
        self.client.force_login(self.superuser)
        response = self.client.get(self._get_url_extrato(self.cliente_loja2.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TEMPLATE_EXTRATO_CLIENTE)
        self.assertEqual(response.context['cliente'], self.cliente_loja2)

    def test_registrar_pagamento_com_sucesso(self):
        """Registra pagamento via POST convertendo vírgula para ponto com sucesso."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {
            'valor': '75,50',
            'forma_pagamento': 'pix',
            'observacao': 'Pagamento parcial via Pix'
        })
        self.assertRedirects(response, self._get_url_extrato(self.cliente_loja1.pk))
        
        pagamento_criado = PagamentoCliente.objects.filter(cliente=self.cliente_loja1, valor=Decimal('75.50')).first()
        self.assertIsNotNone(pagamento_criado)
        self.assertEqual(pagamento_criado.observacao, 'Pagamento parcial via Pix')
        self.assertEqual(pagamento_criado.loja, self.loja1)
        self.assertEqual(pagamento_criado.forma_pagamento, 'pix')

    def test_registrar_pagamento_valor_invalido_redireciona(self):
        """Enviar valor mal formatado ou texto não numérico exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {
            'valor': 'abc',
            'observacao': 'Teste'
        })
        self.assertRedirects(response, self._get_url_extrato(self.cliente_loja1.pk))

    def test_registrar_pagamento_observacao_muito_longa(self):
        """Observação com mais de 255 caracteres exibe mensagem de erro e não cadastra."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {
            'valor': '10.00',
            'observacao': 'a' * 256
        })
        self.assertRedirects(response, self._get_url_extrato(self.cliente_loja1.pk))

    def test_erro_validacao_model_ao_registrar_pagamento(self):
        """Captura ValidationError lançado pelo model durante o full_clean do pagamento."""
        self.client.force_login(self.user_loja1)
        
        err = ValidationError({'valor': ['Valor inválido']})
        with patch('infrastructure.models.venda.PagamentoCliente.full_clean', side_effect=err):
            response = self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {
                'valor': '-10.00'
            })
            self.assertRedirects(response, self._get_url_extrato(self.cliente_loja1.pk))


    def test_extrato_exibe_saldo_e_loja_do_cliente(self):
        PagamentoCliente.objects.create(loja=self.loja1, cliente=self.cliente_loja1, valor=Decimal('12.00'))
        Cliente.objects.filter(pk=self.cliente_loja1.pk).update(telefone='(24) 99999-0000')
        self.client.force_login(self.superuser)

        response = self.client.get(self._get_url_extrato(self.cliente_loja1.pk))

        self.assertEqual(response.context['cliente'].saldo_geral, Decimal('88.00'))  # 150 - 50 - 12
        self.assertContains(response, self.loja1.nome_loja.replace(' ', '%20'))

    def test_pagamento_invalido_informa_o_motivo_e_nao_registra(self):
        self.client.force_login(self.user_loja1)

        response = self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {'valor': '0'})

        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], ["O valor do pagamento deve ser maior que zero."])
        self.assertEqual(PagamentoCliente.objects.filter(cliente=self.cliente_loja1).count(), 1)

    def test_pagamento_sem_observacao_usa_texto_padrao(self):
        self.client.force_login(self.user_loja1)
        self.client.post(self._get_url_extrato(self.cliente_loja1.pk), {'valor': '5', 'forma_pagamento': 'dinheiro', 'observacao': ''})
        novo = PagamentoCliente.objects.filter(cliente=self.cliente_loja1).exclude(pk=self.pagamento_l1.pk).get()
        self.assertEqual(novo.observacao, "Pagamento na caderneta")

    def test_whatsapp_so_aparece_com_telefone(self):
        self.client.force_login(self.user_loja1)
        # O rodapé tem o WhatsApp da CorsariosCode; o do cliente é o que leva a mensagem da caderneta.
        self.assertNotContains(self.client.get(self._get_url_extrato(self.cliente_loja1.pk)), '?text=Ol%C3%A1%2C')

        Cliente.objects.filter(pk=self.cliente_loja1.pk).update(telefone='(24) 99999-0000')
        response = self.client.get(self._get_url_extrato(self.cliente_loja1.pk))

        self.assertContains(response, 'https://wa.me/5524999990000?text=')
        self.assertContains(response, 'ficou%20R%24%20100%2C00%20em%20aberto')

    def test_whatsapp_descreve_credito_como_credito(self):
        """Antes a mensagem dizia "Situação atual: R$ -20.00" para quem tinha crédito."""
        PagamentoCliente.objects.create(loja=self.loja1, cliente=self.cliente_loja1, valor=Decimal('120.00'))
        Cliente.objects.filter(pk=self.cliente_loja1.pk).update(telefone='24999990000')
        self.client.force_login(self.user_loja1)

        response = self.client.get(self._get_url_extrato(self.cliente_loja1.pk))

        self.assertContains(response, 'R%24%2020%2C00%20de%20cr%C3%A9dito')
        self.assertContains(response, 'Crédito: pagou a mais')

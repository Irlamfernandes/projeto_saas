from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from application.a_receber.services import registrar_lembrete
from application.auditoria.services import registrar_alteracao
from application.clientes.exceptions import ClienteComSaldo, SenhaNaoConfere
from application.clientes.services import (
    apagar_dados_pessoais, atualizar_cliente, cadastrar_cliente, registrar_pagamento,
)
from application.vendas.services import cancelar_venda, editar_venda, registrar_venda
from infrastructure.models import Acao, Cliente, LojaModel, Produto, RegistroDeAlteracao, Venda


class Base(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.dono = get_user_model().objects.create_user(username="dono", password="senha-certa", loja=self.loja)
        self.bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('20'), quantidade_estoque=50)
        self.maria = cadastrar_cliente(Cliente(
            loja=self.loja, nome="Maria Souza", telefone="(24) 99999-8888", email="maria@x.com", endereco="Rua A, 10",
        ), self.dono)
        self.joao = cadastrar_cliente(Cliente(loja=self.loja, nome="João"), self.dono)

    def _vender(self, cliente, pago=Decimal('20')):
        venda = registrar_venda(itens=[(self.bolo.pk, 1, None)], cliente=cliente, loja=self.loja, forma_pagamento='pix',
                                usuario=self.dono, valor_pago=pago)
        return venda

    def _registros(self, cliente):
        return RegistroDeAlteracao.objects.filter(clientes=cliente)


class HistoricoLigadoAoClienteTest(Base):

    def test_cada_acao_que_cita_o_cliente_fica_ligada_a_ele(self):
        self.maria.telefone = "(24) 98888-7777"
        atualizar_cliente(self.maria, self.dono)
        venda = self._vender(self.maria)
        editar_venda(venda, itens=[(self.bolo.pk, 1, None)], cliente=self.joao, forma_pagamento='pix', usuario=self.dono)
        registrar_pagamento(self.joao, valor=Decimal('5'), forma_pagamento='pix', usuario=self.dono)
        registrar_lembrete(self.joao, valor=Decimal('5'), usuario=self.dono)
        cancelar_venda(Venda.objects.get(), usuario=self.dono, senha='senha-certa', motivo="teste")

        da_maria = set(self._registros(self.maria).values_list('acao', flat=True))
        do_joao = set(self._registros(self.joao).values_list('acao', flat=True))
        self.assertEqual(da_maria, {Acao.CLIENTE_CADASTRADO, Acao.CLIENTE_EDITADO, Acao.VENDA_REGISTRADA, Acao.VENDA_EDITADA})
        self.assertEqual(do_joao, {Acao.CLIENTE_CADASTRADO, Acao.VENDA_EDITADA, Acao.PAGAMENTO_REGISTRADO,
                                   Acao.LEMBRETE_ENVIADO, Acao.VENDA_CANCELADA})

    def test_venda_de_balcao_nao_liga_ninguem(self):
        registro = registrar_alteracao(loja=self.loja, usuario=None, acao=Acao.VENDA_REGISTRADA, descricao="x", clientes=[None])
        self.assertFalse(registro.clientes.exists())


class ApagarDadosPessoaisTest(Base):

    def test_apaga_do_cadastro_e_do_historico_e_mantem_as_vendas(self):
        venda = self._vender(self.maria)
        self.maria.endereco = "Rua B, 20"
        atualizar_cliente(self.maria, self.dono)

        cliente = apagar_dados_pessoais(self.maria, usuario=self.dono, senha='senha-certa')

        anonimo = f"Cliente removido #{self.maria.pk}"
        self.assertEqual((cliente.nome, cliente.telefone, cliente.email, cliente.endereco), (anonimo, '', '', ''))
        self.assertTrue(cliente.dados_apagados)
        self.assertEqual(Venda.objects.get(pk=venda.pk).cliente, cliente)  # a venda continua, sem o nome

        textos = ' '.join(f"{r.descricao} {r.detalhes}" for r in RegistroDeAlteracao.objects.all())
        for pessoal in ("Maria", "99999-8888", "maria@x.com", "Rua A", "Rua B"):
            self.assertNotIn(pessoal, textos)
        self.assertIn(anonimo, textos)
        self.assertIn("João", textos)  # o que é de outro cliente não muda
        ultimo = RegistroDeAlteracao.objects.filter(acao=Acao.CLIENTE_ANONIMIZADO).get()
        self.assertEqual((ultimo.descricao, list(ultimo.clientes.all())), (anonimo, [cliente]))

    def test_nome_e_contatos_antigos_tambem_saem(self):
        self._vender(self.maria)  # "Venda #1 · Maria Souza · ..."
        self.maria.nome, self.maria.telefone = "Maria S.", "(24) 97777-6666"
        atualizar_cliente(self.maria, self.dono)

        apagar_dados_pessoais(self.maria, usuario=self.dono, senha='senha-certa')

        textos = ' '.join(f"{r.descricao} {r.detalhes}" for r in RegistroDeAlteracao.objects.all())
        for pessoal in ("Maria", "99999-8888", "97777-6666"):
            self.assertNotIn(pessoal, textos)

    def test_nome_maior_e_trocado_antes_do_menor(self):
        """"Maria Souza" sai inteiro, e não vira "Cliente removido #1 Souza" por causa de um pedaço."""
        from application.clientes.services import _trocar
        self.assertEqual(_trocar({'a': ["Maria Souza · Maria"]}, {"Maria": "X", "Maria Souza": "Y"}), {'a': ["Y · X"]})
        self.assertEqual(_trocar(10, {"1": "x"}), 10)

    def test_exige_a_senha(self):
        with self.assertRaises(SenhaNaoConfere):
            apagar_dados_pessoais(self.maria, usuario=self.dono, senha='errada')
        self.maria.refresh_from_db()
        self.assertEqual(self.maria.nome, "Maria Souza")

    def test_com_saldo_na_caderneta_nao_apaga(self):
        self._vender(self.maria, pago=Decimal('0'))
        with self.assertRaisesMessage(ClienteComSaldo, "Este cliente ainda deve R$ 20,00 na caderneta."):
            apagar_dados_pessoais(self.maria, usuario=self.dono, senha='senha-certa')

        registrar_pagamento(self.maria, valor=Decimal('30'), forma_pagamento='pix', usuario=self.dono)
        with self.assertRaisesMessage(ClienteComSaldo, "tem R$ 10,00 de crédito"):
            apagar_dados_pessoais(Cliente.objects.get(pk=self.maria.pk), usuario=self.dono, senha='senha-certa')

    def test_cliente_normal_nao_esta_apagado(self):
        self.assertFalse(self.maria.dados_apagados)


class RegistroSemDataTest(TestCase):

    def test_registro_criado_agora(self):
        loja = LojaModel.objects.create(nome_loja="L")
        registro = registrar_alteracao(loja=loja, usuario=None, acao=Acao.CLIENTE_EDITADO, descricao="x")
        self.assertLessEqual(registro.data, timezone.now())

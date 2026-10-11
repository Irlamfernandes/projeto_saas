from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from application.clientes.services import apagar_dados_pessoais, atualizar_cliente, cadastrar_cliente
from infrastructure.admin.registro_de_alteracao_admin import sem_contatos
from infrastructure.models import Cliente, LojaModel, RegistroDeAlteracao
from interfaces.forms import ClienteForm
from interfaces.views.comum import primeiro_erro

User = get_user_model()
CPF = '52998224725'
CPF_FORMATADO = '529.982.247-25'


class CpfNoFormularioTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")

    def _form(self, cpf, instancia=None):
        return ClienteForm({'nome': 'Ana', 'cpf': cpf}, instance=instancia or Cliente(loja=self.loja))

    def test_aceita_com_ou_sem_pontos_e_guarda_so_os_digitos(self):
        for digitado in (CPF, CPF_FORMATADO, ' 529 982 247 25 '):
            with self.subTest(digitado):
                form = self._form(digitado)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['cpf'], CPF)

    def test_e_opcional(self):
        form = self._form('')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().cpf, '')

    def test_cpf_invalido_ou_comprido_demais(self):
        for digitado in ('529.982.247-26', '111.111.111-11', '1' * 21):
            with self.subTest(digitado):
                form = self._form(digitado)
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), "Informe um CPF válido.")

    def test_nao_repete_na_mesma_loja_mas_pode_em_outra(self):
        Cliente.objects.create(loja=self.loja, nome="Bia", cpf=CPF)
        Cliente.objects.create(loja=self.loja, nome="Sem CPF 1")

        repetido = self._form(CPF_FORMATADO)
        self.assertFalse(repetido.is_valid())
        self.assertEqual(primeiro_erro(repetido), "Já existe um cliente com este CPF.")

        outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.assertTrue(ClienteForm({'nome': 'Ana', 'cpf': CPF}, instance=Cliente(loja=outra_loja)).is_valid())
        self.assertTrue(self._form('').is_valid())  # vários clientes sem CPF na mesma loja

    def test_editar_o_proprio_cliente_mantendo_o_cpf(self):
        bia = Cliente.objects.create(loja=self.loja, nome="Bia", cpf=CPF)
        self.assertTrue(self._form(CPF, instancia=bia).is_valid())


class CpfNasTelasTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.usuario = User.objects.create_user(username='dono', password='senha-123', loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(self.usuario)

    def test_cadastrar_sem_cpf_e_colocar_depois_na_edicao(self):
        self.client.post(reverse('clientes'), {'nome': 'Ana', 'cpf': ''})
        ana = Cliente.objects.get(nome='Ana')
        self.assertEqual(ana.cpf, '')

        self.client.post(reverse('editar_cliente', args=[ana.pk]), {'nome': 'Ana', 'cpf': CPF_FORMATADO})

        ana.refresh_from_db()
        self.assertEqual(ana.cpf, CPF)
        alteracao = RegistroDeAlteracao.objects.filter(clientes=ana).latest('pk')
        self.assertEqual(alteracao.detalhes['alteracoes']['cpf'], ['', CPF])

    def test_lista_e_caderneta_mostram_o_cpf_formatado_e_a_busca_acha(self):
        ana = Cliente.objects.create(loja=self.loja, nome="Ana", cpf=CPF)
        Cliente.objects.create(loja=self.loja, nome="Bia")

        lista = self.client.get(reverse('clientes'), {'q': '529.982'})
        self.assertContains(lista, f'CPF {CPF_FORMATADO}')
        self.assertContains(lista, f'data-cpf="{CPF_FORMATADO}"')
        self.assertNotContains(lista, 'Bia')
        self.assertContains(self.client.get(reverse('extrato_cliente', args=[ana.pk])), f'CPF {CPF_FORMATADO}')

    def test_busca_sem_numero_nao_filtra_por_cpf(self):
        Cliente.objects.create(loja=self.loja, nome="Ana", cpf=CPF)
        self.assertNotContains(self.client.get(reverse('clientes'), {'q': 'Bia'}), 'Ana')


class CpfNaLgpdTest(TestCase):

    def test_apagar_dados_pessoais_apaga_o_cpf_do_cadastro_e_do_historico(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        dono = User.objects.create_user(username='dono', password='senha-123', loja=loja, deve_trocar_senha=False)
        ana = cadastrar_cliente(Cliente(loja=loja, nome="Ana", cpf=CPF), usuario=dono)
        ana.cpf = '10000000108'
        atualizar_cliente(ana, usuario=dono)

        apagar_dados_pessoais(ana, usuario=dono, senha='senha-123')

        ana.refresh_from_db()
        self.assertEqual(ana.cpf, '')
        historico = str(list(RegistroDeAlteracao.objects.filter(clientes=ana).values_list('detalhes', flat=True)))
        self.assertNotIn(CPF, historico)
        self.assertNotIn('10000000108', historico)

    def test_admin_esconde_o_cpf(self):
        self.assertEqual(sem_contatos({'cliente': {'nome': 'Ana', 'cpf': CPF}}), {'cliente': {'nome': 'Ana', 'cpf': '(oculto)'}})

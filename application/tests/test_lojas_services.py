import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from application.lojas.exceptions import FalhaNoEnvioDaMarca, MarcaInvalida, UsuarioSemLoja
from application.lojas.services import LADO_MAXIMO_DA_MARCA, remover_marca, trocar_marca
from infrastructure.models import Acao, LojaModel, RegistroDeAlteracao
from tests.apoio import URL_PUBLICA, StorageFalso, imagem_de_teste


class StorageQueGuardaArquivos(StorageFalso):
    def enviar(self, arquivo, pasta):
        self.ultimo_arquivo = arquivo.read()
        return super().enviar(arquivo, pasta)


class TrocarMarcaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria")
        self.storage = StorageFalso()

    def test_envia_a_marca_otimizada_e_salva_a_url(self):
        trocar_marca(self.loja, imagem_de_teste('logo.png'), usuario=None, storage=self.storage)

        self.loja.refresh_from_db()
        self.assertEqual(self.loja.logo_url, f"{URL_PUBLICA}/lojas/logo.webp")
        self.assertEqual(self.storage.enviados, [self.loja.logo_url])

    def test_reduz_a_marca_para_no_maximo_512px(self):
        grande = io.BytesIO()
        Image.new('RGB', (2000, 1000), 'blue').save(grande, 'PNG')
        storage = StorageQueGuardaArquivos()

        trocar_marca(self.loja, SimpleUploadedFile('grande.png', grande.getvalue()), usuario=None, storage=storage)

        with Image.open(io.BytesIO(storage.ultimo_arquivo)) as enviada:
            self.assertEqual((enviada.format, enviada.size), ('WEBP', (LADO_MAXIMO_DA_MARCA, 256)))

    def test_trocar_apaga_a_marca_antiga_depois_de_salvar(self):
        self.loja.logo_url = f"{URL_PUBLICA}/lojas/antiga.webp"
        self.loja.save()

        with self.captureOnCommitCallbacks(execute=True):
            trocar_marca(self.loja, imagem_de_teste('nova.png'), usuario=None, storage=self.storage)

        self.assertEqual(self.storage.removidos, [f"{URL_PUBLICA}/lojas/antiga.webp"])

    def test_registra_no_historico(self):
        trocar_marca(self.loja, imagem_de_teste(), usuario=None, storage=self.storage)
        registro = RegistroDeAlteracao.objects.get()
        self.assertEqual((registro.acao, registro.descricao), (Acao.MARCA_ALTERADA, "Nova marca enviada"))

    def test_imagem_ilegivel_nao_altera_nada(self):
        with self.assertRaises(MarcaInvalida):
            trocar_marca(self.loja, SimpleUploadedFile('x.png', b'nao e imagem'), usuario=None, storage=self.storage)
        self.assertEqual(self.storage.enviados, [])
        self.assertFalse(RegistroDeAlteracao.objects.exists())

    def test_falha_no_storage_nao_altera_nada(self):
        with self.assertRaises(FalhaNoEnvioDaMarca), self.assertLogs('application.lojas.services', 'ERROR'):
            trocar_marca(self.loja, imagem_de_teste(), usuario=None, storage=StorageFalso(falhar_no_envio=0))
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.logo_url, '')

    def test_usuario_sem_loja_e_recusado(self):
        with self.assertRaises(UsuarioSemLoja):
            trocar_marca(None, imagem_de_teste(), usuario=None, storage=self.storage)


class RemoverMarcaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria", logo_url=f"{URL_PUBLICA}/lojas/logo.webp")
        self.storage = StorageFalso()

    def test_limpa_a_url_apaga_o_arquivo_e_registra(self):
        with self.captureOnCommitCallbacks(execute=True):
            remover_marca(self.loja, usuario=None, storage=self.storage)

        self.loja.refresh_from_db()
        self.assertEqual(self.loja.logo_url, '')
        self.assertEqual(self.storage.removidos, [f"{URL_PUBLICA}/lojas/logo.webp"])
        self.assertEqual(RegistroDeAlteracao.objects.get().descricao, "Marca removida")

    def test_loja_sem_marca_nao_faz_nada(self):
        self.loja.logo_url = ''
        remover_marca(self.loja, usuario=None, storage=self.storage)
        self.assertFalse(RegistroDeAlteracao.objects.exists())

    def test_usuario_sem_loja_e_recusado(self):
        with self.assertRaises(UsuarioSemLoja):
            remover_marca(None, usuario=None, storage=self.storage)

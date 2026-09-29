import uuid
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel


class LojaModelTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(
            nome_loja="Loja Central",
            ativo=True
        )

    # ---------------------------------------------------------
    # Testes Básicos (Campos, UUID e __str__)
    # ---------------------------------------------------------
    def test_loja_str(self):
        """O método __str__ deve retornar o nome da loja."""
        self.assertEqual(str(self.loja), "Loja Central")

    def test_loja_creation(self):
        """Verifica se os campos da loja são salvos e gerados corretamente."""
        self.assertIsInstance(self.loja.id, uuid.UUID)
        self.assertEqual(self.loja.nome_loja, "Loja Central")
        self.assertTrue(self.loja.ativo)
        self.assertIsNotNone(self.loja.criado_em)

    def test_loja_default_ativo(self):
        """O campo ativo deve ter True como valor padrão."""
        loja_padrao = LojaModel.objects.create(nome_loja="Loja Padrão")
        self.assertTrue(loja_padrao.ativo)

    def test_loja_meta_options(self):
        """Verifica as configurações de Meta do modelo."""
        self.assertEqual(LojaModel._meta.db_table, 'lojas')
        self.assertEqual(str(LojaModel._meta.verbose_name), 'Loja')
        self.assertEqual(str(LojaModel._meta.verbose_name_plural), 'Lojas')

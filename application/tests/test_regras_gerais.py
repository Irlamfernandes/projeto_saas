"""Regras que valem para toda a camada de aplicação."""
from django.test import SimpleTestCase
import application
from tests.apoio import dataclasses_do_pacote


class ResultadosImutaveisTest(SimpleTestCase):
    """O que os serviços e consultas devolvem não pode ser alterado por quem recebe (tela, relatório, outro serviço)."""

    def test_toda_dataclass_da_aplicacao_e_congelada(self):
        classes = dataclasses_do_pacote(application)
        self.assertGreaterEqual(len(classes), 27)
        for classe in classes:
            with self.subTest(classe.__qualname__):
                self.assertTrue(classe.__dataclass_params__.frozen)

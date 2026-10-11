from django.test import SimpleTestCase
from infrastructure.utils.cpf import cpf_valido, formatar_cpf, so_digitos


class CpfTest(SimpleTestCase):

    def test_so_digitos(self):
        self.assertEqual(so_digitos(' 529.982.247-25 '), '52998224725')
        self.assertEqual(so_digitos(None), '')

    def test_cpfs_validos_inclusive_com_digito_zero(self):
        # O 2º e o 3º são casos em que a conta de um dos verificadores dá resto 10 (vira 0) e resto 0.
        for cpf in ('52998224725', '10000000108', '10000000604', '10000002810'):
            with self.subTest(cpf):
                self.assertTrue(cpf_valido(cpf))

    def test_cpfs_invalidos(self):
        casos = {
            'primeiro verificador errado': '52998224735',
            'segundo verificador errado': '52998224726',
            'todos iguais': '11111111111',
            'curto': '5299822472',
            'longo': '529982247250',
            'vazio': '',
        }
        for caso, cpf in casos.items():
            with self.subTest(caso):
                self.assertFalse(cpf_valido(cpf))

    def test_formatar(self):
        self.assertEqual(formatar_cpf('52998224725'), '529.982.247-25')
        self.assertEqual(formatar_cpf(''), '')
        self.assertEqual(formatar_cpf('123'), '123')

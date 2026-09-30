import io
from django.core.management import call_command
from django.test import TestCase


class MigracoesEmDiaTest(TestCase):
    """O banco de produção é criado pelas migrações: mudar um campo sem gerar a migração deixaria os dois diferentes."""

    def test_os_modelos_batem_com_as_migracoes(self):
        saida = io.StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', stdout=saida, stderr=saida)
        except SystemExit:  # o --check sai com erro quando falta migração
            self.fail(f"Falta migração:\n{saida.getvalue()}")

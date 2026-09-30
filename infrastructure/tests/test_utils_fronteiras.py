"""Detalhes exatos dos utilitários (achados pelo teste de mutação): layout do PDF, planilha e fotos."""
import io
import json
import logging
import sys
import threading
import traceback
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import requests as requests_lib
from django.core.management import CommandError
from django.test import SimpleTestCase
from PIL import Image
from requests.exceptions import RequestException
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, Spacer, Table
from infrastructure import registro_de_erros
from infrastructure.management.commands.fazer_backup import Command as FazerBackup
from infrastructure.management.commands.restaurar_backup import Command as RestaurarBackup
from infrastructure.pagamentos.mercado_pago import MercadoPago, PagamentoConsultado
from infrastructure.tests.test_otimizacao_de_imagem import _foto
from infrastructure.tests.test_relatorios_export import _abrir_excel, _relatorio
from infrastructure.utils import backup_cripto, relatorios_export as exportacao
from infrastructure.registro_de_erros import GuardarErroNoBanco
from infrastructure.utils.backup_cripto import ChaveDeBackupInvalida
from infrastructure.utils.formatacao import item, numero
from infrastructure.utils.supabase_backups import BackupsNoSupabase
from infrastructure.utils.supabase_storage import SupabaseStorage, gerar_nome_unico
from infrastructure.utils.otimizacao_de_imagem import ImagemIlegivel, _tem_transparencia, otimizar_imagem
from infrastructure.utils.relatorios_export import (
    CREDITO, DEVENDO, ESTOQUE, RESUMO, TEMPORAL, _rodape_da_pagina, gerar_relatorio_pdf,
)


def _montar_pdf(tipo='resumo', **opcoes):
    """Gera o PDF sem desenhar: devolve (parâmetros do documento, conteúdo, argumentos do build)."""
    with patch.object(exportacao, 'SimpleDocTemplate') as documento:
        gerar_relatorio_pdf(tipo, _relatorio(), io.BytesIO(), **opcoes)
    story = documento.return_value.build.call_args.args[0]
    return documento.call_args, story, documento.return_value.build.call_args.kwargs


class SecoesDoRelatorioTest(SimpleTestCase):

    def test_titulos_abas_cabecalhos_e_larguras(self):
        self.assertEqual(
            [(s.titulo, s.aba, s.cabecalho, s.larguras_pdf) for s in (RESUMO, TEMPORAL, DEVENDO, CREDITO, ESTOQUE)],
            [
                ("Resumo Executivo e Indicadores", "Resumo Executivo", ("Indicador", "Valor"), (300, 212)),
                ("Desempenho por Ciclo Temporal", "Desempenho Temporal", ("Período", "Faturamento"), (300, 212)),
                ("Relatório de Clientes Devendo (Fiado)", "Clientes Devendo", ("Cliente", "Valor Devido"), (300, 212)),
                ("Relatório de Clientes com Crédito", "Clientes com Crédito", ("Cliente", "Crédito Disponível"), (300, 212)),
                ("Inventário de Estoque Completo", "Estoque", ("Produto", "Preço de Venda", "Qtd em Estoque", "Unidade"),
                 (220, 110, 110, 72)),
            ],
        )

    def test_linhas_do_resumo(self):
        self.assertEqual([rotulo for rotulo, _ in RESUMO.linhas(_relatorio())],
                         ["Faturamento Total", "Ticket Médio", "Total a Receber (Fiado)", "Crédito de Clientes"])

    def test_formato_de_dinheiro_na_planilha(self):
        self.assertEqual(_abrir_excel('estoque').active['B2'].number_format, '#,##0.00')


class LayoutDoPdfTest(SimpleTestCase):

    def test_pagina_margens_e_rodape(self):
        documento, _story, build = _montar_pdf()
        self.assertEqual(documento.kwargs, {'pagesize': letter, 'rightMargin': 30, 'leftMargin': 30, 'topMargin': 30,
                                            'bottomMargin': 40})
        self.assertIs(build['onFirstPage'], build['onLaterPages'])
        self.assertEqual(build['onFirstPage'].keywords['assinatura'], '')

    def test_titulo_espacos_e_tabela_de_cada_secao(self):
        _documento, story, _build = _montar_pdf('estoque')
        titulo, antes, tabela, depois = story
        self.assertEqual([type(item) for item in story], [Paragraph, Spacer, Table, Spacer])
        self.assertEqual(titulo.text, "<b>Inventário de Estoque Completo</b>")
        estilo = titulo.style
        self.assertEqual((estilo.name, estilo.parent.name, estilo.fontSize, estilo.textColor, estilo.spaceAfter),
                         ('TituloRelatorio', 'Heading1', 16, colors.HexColor('#1f2937'), 10))
        self.assertEqual(((antes.width, antes.height), (depois.width, depois.height)), ((1, 10), (1, 15)))
        self.assertEqual(tabela._argW, [220, 110, 110, 72])
        self.assertEqual(exportacao._ESTILO_TABELA.getCommands(), [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ])

    def test_cabecalho_da_loja(self):
        with patch.object(exportacao, 'cabecalho_da_loja', return_value=[]) as cabecalho:
            _montar_pdf(loja='LOJA', storage='STORAGE')
        cabecalho.assert_called_once_with('LOJA', "Relatório", 'STORAGE')

    def test_fonte_do_rodape(self):
        canvas = MagicMock()
        documento = MagicMock(leftMargin=30, rightMargin=30, pagesize=(612, 792), page=1)
        _rodape_da_pagina(canvas, documento, gerado_em=datetime(2026, 9, 29), assinatura='')
        canvas.setFont.assert_called_once_with('Helvetica', 7.5)
        canvas.setFillColor.assert_called_once_with(colors.HexColor('#9ca3af'))


class FotosTest(SimpleTestCase):

    def test_qualidade_do_webp(self):
        foto = _foto((20, 20))
        with patch.object(Image.Image, 'save', autospec=True) as gravar:
            otimizar_imagem(foto)
        self.assertEqual(gravar.call_args.kwargs, {'format': 'WEBP', 'quality': 70})

    def test_mensagem_de_arquivo_ilegivel(self):
        falso = io.BytesIO(b'texto')
        falso.name = 'nota.png'
        with self.assertRaises(ImagemIlegivel) as erro:
            otimizar_imagem(falso)
        self.assertEqual(str(erro.exception), "Não foi possível ler a imagem 'nota.png'.")

    def test_modos_com_transparencia(self):
        paleta = Image.new('P', (1, 1))
        com_cor_transparente = Image.new('P', (1, 1))
        com_cor_transparente.info['transparency'] = 0
        casos = {'LA': Image.new('LA', (1, 1)), 'PA': Image.new('PA', (1, 1)), 'RGBA': Image.new('RGBA', (1, 1)),
                 'P': paleta, 'P + transparency': com_cor_transparente, 'RGB': Image.new('RGB', (1, 1))}
        self.assertEqual({nome: _tem_transparencia(imagem) for nome, imagem in casos.items()},
                         {'LA': True, 'PA': True, 'RGBA': True, 'P': False, 'P + transparency': True, 'RGB': False})


# Backup de referência: b'{"ok": 1}' com a senha abaixo, sal 00..0f e nonce 00..0b. Se não abrir mais, backups
# antigos também deixaram de abrir (mudou o cabeçalho, o scrypt ou a ordem das partes).
BACKUP_DE_REFERENCIA = bytes.fromhex(
    '474c424b503031000102030405060708090a0b0c0d0e0f000102030405060708090a0be8fd514134cfe4ccdd71d4c03106302b38c526fa3c9a'
    '04da5405461886aaa276b21747329efea3866ad777df68'
)


class BackupCriptografadoTest(SimpleTestCase):

    def abrir(self, conteudo, senha='senha-de-referencia'):
        with tempfile.NamedTemporaryFile() as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            saida = io.BytesIO()
            backup_cripto.descriptografar(arquivo.name, saida, senha)
        return saida.getvalue()

    def test_backup_de_referencia_continua_abrindo(self):
        self.assertEqual(self.abrir(BACKUP_DE_REFERENCIA), b'{"ok": 1}')

    def test_gera_exatamente_o_formato_de_referencia(self):
        saida = io.BytesIO()
        with patch.object(backup_cripto.os, 'urandom', side_effect=lambda tamanho: bytes(range(tamanho))):
            backup_cripto.criptografar(io.BytesIO(b'{"ok": 1}'), saida, 'senha-de-referencia')
        self.assertEqual(saida.getvalue(), BACKUP_DE_REFERENCIA)

    def test_tamanho_minimo(self):
        cabecalho = BACKUP_DE_REFERENCIA[:35]  # GLBKP01 + sal + nonce
        with self.assertRaises(ChaveDeBackupInvalida) as erro:
            self.abrir(cabecalho + bytes(15))  # um byte a menos que cabeçalho + tag
        self.assertEqual(str(erro.exception), "Este arquivo não é um backup do sistema.")
        with self.assertRaises(ChaveDeBackupInvalida) as erro:
            self.abrir(cabecalho + bytes(16))
        self.assertEqual(str(erro.exception), "Senha errada ou arquivo alterado/corrompido.")

    def test_sem_senha(self):
        with self.assertRaises(ChaveDeBackupInvalida) as erro:
            backup_cripto.criptografar(io.BytesIO(b''), io.BytesIO(), '')
        self.assertEqual(str(erro.exception), "Defina BACKUP_CHAVE no ambiente.")

    def test_le_em_blocos_de_1_mb(self):
        entrada = MagicMock()
        entrada.read.side_effect = [b'a', b'']
        backup_cripto.criptografar(entrada, io.BytesIO(), 'x')
        entrada.read.assert_called_with(1_048_576)


def _erro(chamada):
    try:
        chamada()
    except Exception as erro:  # noqa: BLE001
        return str(erro)
    raise AssertionError("não deu erro")


@patch('infrastructure.utils.supabase_storage.requests')
class SupabaseStorageDetalhesTest(SimpleTestCase):

    def setUp(self):
        self.storage = SupabaseStorage('https://xyz.supabase.co/', 'chave')
        self.foto = io.BytesIO(b'x')
        self.foto.name = 'a.png'

    def test_prazo_mensagens_e_codigos_aceitos(self, requests):
        requests.RequestException = RequestException
        requests.post.return_value = MagicMock(status_code=201)
        self.storage.enviar(self.foto, 'p')
        self.assertEqual(requests.post.call_args.kwargs['timeout'], 10)
        requests.post.return_value = MagicMock(status_code=202, text='?')
        self.assertEqual(_erro(lambda: self.storage.enviar(self.foto, 'p')), "Erro na API do Supabase (202): ?")
        requests.post.side_effect = RequestException('sem rede')
        self.assertEqual(_erro(lambda: self.storage.enviar(self.foto, 'p')),
                         "Erro de comunicação com o Supabase Storage: sem rede")
        self.assertEqual(_erro(lambda: SupabaseStorage('', '').enviar(self.foto, 'p')),
                         "Credenciais do Supabase não configuradas no .env.")

    def test_url_publica_exata(self, requests):
        requests.post.return_value = MagicMock(status_code=200)
        url = self.storage.enviar(self.foto, 'p')
        self.assertTrue(url.startswith('https://xyz.supabase.co/storage/v1/object/public/imagens/p/'))
        self.assertTrue(url.endswith('.png'))

    def test_remover_aceita_200_e_204_e_registra_o_resto(self, requests):
        requests.RequestException = RequestException
        url = 'https://xyz.supabase.co/storage/v1/object/public/imagens/p/a.png'
        for status in (200, 204):
            requests.delete.return_value = MagicMock(status_code=status)
            with self.assertNoLogs('infrastructure.utils.supabase_storage'):
                self.storage.remover(url)
        requests.delete.return_value = MagicMock(status_code=201)
        with self.assertLogs('infrastructure.utils.supabase_storage', 'WARNING') as log:
            self.storage.remover(url)
        self.assertEqual(log.records[0].getMessage(), "Supabase recusou remover p/a.png (201)")
        requests.delete.side_effect = RequestException('x')
        with self.assertLogs('infrastructure.utils.supabase_storage', 'WARNING') as log:
            self.storage.remover(url)
        self.assertEqual(log.records[0].getMessage(), "Falha ao remover imagem p/a.png do Supabase")
        self.assertIs(log.records[0].exc_info[0], RequestException)
        requests.delete.reset_mock()
        for vazia in (None, ''):
            self.storage.remover(vazia)
        requests.delete.assert_not_called()

    def test_baixar(self, requests):
        requests.RequestException = RequestException
        requests.get.side_effect = RequestException('x')
        url = 'https://xyz.supabase.co/storage/v1/object/public/imagens/p/a.png'
        with self.assertLogs('infrastructure.utils.supabase_storage', 'WARNING') as log:
            self.assertIsNone(self.storage.baixar(url))
        self.assertEqual(log.records[0].getMessage(), f"Falha ao baixar {url} do Supabase")
        self.assertIs(log.records[0].exc_info[0], RequestException)
        self.assertIsNone(self.storage.baixar(None))

    def test_nomes_e_enderecos(self, _requests):
        self.assertNotIn('.', gerar_nome_unico('x.$a'))
        self.assertEqual(SupabaseStorage._normalizar_base_url(' https://ABCX/ '), 'https://ABCX')


class SupabaseBackupsDetalhesTest(SimpleTestCase):

    def pedir(self, *respostas):
        return patch('requests.request', side_effect=list(respostas))

    def test_envio_baixa_e_prazos(self):
        arquivo = tempfile.NamedTemporaryFile()  # noqa: SIM115 (fechado no fim do teste)
        self.addCleanup(arquivo.close)
        backups = BackupsNoSupabase('https://abc.supabase.co', 'segredo')
        with self.pedir(MagicMock(status_code=400), MagicMock(status_code=200), MagicMock(status_code=200)) as pedido:
            backups.enviar(arquivo.name, 'b.enc')
        envio = pedido.call_args.kwargs
        self.assertEqual((envio['timeout'], envio['headers']['apikey'], envio['headers']['Content-Type']),
                         (120, 'segredo', 'application/octet-stream'))
        resposta = MagicMock(status_code=200)
        resposta.iter_content.return_value = []
        with self.pedir(resposta) as pedido:
            backups.baixar('b.enc', io.BytesIO())
        self.assertIs(pedido.call_args.kwargs['stream'], True)
        resposta.iter_content.assert_called_once_with(1_048_576)

    def test_mensagens(self):
        backups = BackupsNoSupabase('https://abc.supabase.co', 'segredo')
        publico = MagicMock(status_code=200)
        publico.json.return_value = {'public': True}
        with self.pedir(publico):
            self.assertEqual(_erro(lambda: backups.enviar('x', 'b.enc')),
                             "O bucket 'backups' está público no Supabase: deixe-o privado antes do backup.")
        with self.pedir(MagicMock(status_code=500, text='e' * 400)):
            self.assertEqual(_erro(lambda: backups.remover('b.enc')), f"Erro na API do Supabase (500): {'e' * 300}")
        with patch('requests.request', side_effect=requests_lib.ConnectionError('sem rede')):
            self.assertEqual(_erro(lambda: backups.remover('b.enc')), "Erro de comunicação com o Supabase Storage: sem rede")
        for url, chave in (('https://abc.supabase.co', ''), ('', 'segredo')):
            with self.subTest(url=url, chave=chave):
                self.assertEqual(_erro(partial(BackupsNoSupabase(url, chave).remover, 'b.enc')),
                                 "Credenciais do Supabase não configuradas.")


def _resposta_mp(status=200, dados=None, ilegivel=False):
    item = MagicMock(status_code=status)
    if ilegivel:
        item.json.side_effect = ValueError('não é json')
    else:
        item.json.return_value = dados
    return item


@patch('infrastructure.pagamentos.mercado_pago.requests')
class MercadoPagoDetalhesTest(SimpleTestCase):

    def setUp(self):
        self.mp = MercadoPago('TEST-token')

    def pix(self):
        return self.mp.criar_pix(valor=Decimal('1'), descricao='d', email='a@b.co', referencia='ref-1',
                                 expira_em=datetime(2026, 9, 29, tzinfo=UTC))

    def test_endereco_prazo_e_cabecalhos(self, requests):
        requests.post.return_value = _resposta_mp(201, {'id': 1, 'point_of_interaction': {'transaction_data': {
            'qr_code': 'c', 'qr_code_base64': 'b'}}})
        self.pix()
        self.assertEqual(requests.post.call_args.args, ('https://api.mercadopago.com/v1/payments',))
        opcoes = requests.post.call_args.kwargs
        self.assertEqual((opcoes['timeout'], opcoes['headers']),
                         (15, {'Authorization': 'Bearer TEST-token', 'X-Idempotency-Key': 'ref-1'}))

    def test_mensagens(self, requests):
        requests.RequestException = RequestException
        requests.post.return_value = _resposta_mp(201, {'id': 1})
        self.assertEqual(_erro(self.pix), "Resposta do Mercado Pago sem os dados do Pix.")
        requests.post.return_value = _resposta_mp(200, ilegivel=True)
        self.assertEqual(_erro(self.pix), "Resposta do Mercado Pago ilegível.")
        requests.post.return_value = _resposta_mp(500)
        with self.assertLogs('infrastructure.pagamentos.mercado_pago', 'ERROR') as log:
            self.assertEqual(_erro(self.pix), "Mercado Pago respondeu 500.")
        self.assertEqual(log.records[0].getMessage(),
                         "Mercado Pago respondeu 500 em POST https://api.mercadopago.com/v1/payments")
        requests.post.side_effect = RequestException('sem rede')
        self.assertEqual(_erro(self.pix), "Erro de comunicação com o Mercado Pago: sem rede")
        self.assertEqual(_erro(partial(MercadoPago('').consultar, '1')),
                         "MERCADO_PAGO_ACCESS_TOKEN não configurado no .env.")

    def test_explicacao_da_recusa(self, requests):
        casos = [
            ({'cause': [{'description': 'e-mail inválido'}, {'description': 'valor baixo'}]}, "e-mail inválido; valor baixo"),
            ({'cause': [{'code': 1}], 'message': 'recusado'}, "recusado"),
            ({}, ""),
        ]
        for dados, esperado in casos:
            with self.subTest(esperado):
                requests.post.return_value = _resposta_mp(400, dados)
                self.assertEqual(_erro(self.pix), esperado)
        requests.post.return_value = _resposta_mp(422, ilegivel=True)
        self.assertEqual(_erro(self.pix), "")

    def test_consulta_sem_campos(self, requests):
        requests.get.return_value = _resposta_mp(200, {})
        self.assertEqual(self.mp.consultar('9'), PagamentoConsultado('', '', None, '', ''))


class ComandosDeBackupTest(SimpleTestCase):

    def test_ajuda(self):
        fazer, restaurar = FazerBackup(), RestaurarBackup()
        self.assertEqual(fazer.help, "Faz um backup dos dados agora (ou, com --agendado, só se estiver na hora).")
        self.assertEqual(restaurar.help, "Restaura os dados de um arquivo de backup num banco novo (já com o migrate rodado).")
        opcoes = {acao.dest: acao.help for acao in fazer.create_parser('manage.py', 'fazer_backup')._actions}
        self.assertEqual(opcoes['agendado'], "respeita liga/desliga e intervalo do admin")
        opcoes = {acao.dest: acao.help for acao in restaurar.create_parser('manage.py', 'restaurar_backup')._actions}
        self.assertEqual(opcoes['chave'], "senha do backup (padrão: BACKUP_CHAVE do ambiente)")

    def test_sem_opcao_o_backup_e_manual_e_as_mensagens_sao_exatas(self):
        comando = FazerBackup(stdout=io.StringIO())
        comando.style.SUCCESS = str

        def pedir(origem, executar):
            executar(lambda: SimpleNamespace(sucesso=True, arquivo='b.enc', tamanho=10))
            return True, ''
        with patch('infrastructure.management.commands.fazer_backup.pedir_backup', side_effect=pedir) as pedido:
            comando.handle()
        self.assertEqual(pedido.call_args.args, ('manual',))
        self.assertEqual(comando.stdout.getvalue(), "Backup b.enc guardado (10 bytes).\n")

        def falhar(origem, executar):
            executar(lambda: SimpleNamespace(sucesso=False, erro='disco cheio'))
            return True, ''
        with patch('infrastructure.management.commands.fazer_backup.pedir_backup', side_effect=falhar), \
                self.assertRaises(CommandError) as erro:
            comando.handle()
        self.assertEqual(str(erro.exception), "O backup falhou: disco cheio")

    def test_restaurar_avisa_quando_termina(self):
        comando = RestaurarBackup(stdout=io.StringIO())
        comando.style.SUCCESS = str
        with patch('infrastructure.management.commands.restaurar_backup.restaurar'):
            comando.handle(arquivo='b.enc')
        self.assertEqual(comando.stdout.getvalue(), "Dados restaurados.\n")


class RegistroDeErrosDetalhesTest(SimpleTestCase):

    def registro(self, exc_info=None, request=None):
        registro = logging.LogRecord('app', logging.ERROR, __file__, 42, 'falhou', (), exc_info)
        if request is not None:
            registro.request = request
        return registro

    def test_bibliotecas_do_sistema_nao_sao_do_projeto(self):
        self.assertFalse(registro_de_erros._do_projeto(f"{registro_de_erros.RAIZ}/venv/lib/dist-packages/x.py"))

    def test_local_e_o_ultimo_ponto_do_nosso_codigo(self):
        try:
            json.loads('não é json')
        except ValueError:
            info = sys.exc_info()
        ocorrencia = registro_de_erros.ocorrencia_do_registro(self.registro(info))
        self.assertTrue(ocorrencia.local.startswith('infrastructure/tests/test_utils_fronteiras.py:'), ocorrencia.local)
        self.assertEqual(ocorrencia.detalhes, ''.join(traceback.format_exception(info[1])))

    def test_excecao_sem_caminho_usa_a_linha_do_log(self):
        erro = ValueError('sem traceback')
        ocorrencia = registro_de_erros.ocorrencia_do_registro(self.registro((ValueError, erro, None)))
        self.assertEqual((ocorrencia.tipo, ocorrencia.local), ('ValueError', 'infrastructure/tests/test_utils_fronteiras.py:42'))

    def test_pedido_sem_metodo(self):
        ocorrencia = registro_de_erros.ocorrencia_do_registro(self.registro(request=SimpleNamespace(path='/x')))
        self.assertEqual((ocorrencia.caminho, ocorrencia.metodo), ('/x', ''))

    def test_grava_uma_vez_por_erro_mesmo_se_a_gravacao_registrar_outro(self):
        gravados = []

        def gravar(ocorrencia):
            gravados.append(ocorrencia)
            GuardarErroNoBanco().emit(self.registro())  # erro dentro da gravação: não pode virar laço
        with patch('application.erros.services.registrar_erro', side_effect=gravar):
            GuardarErroNoBanco().emit(self.registro())
            GuardarErroNoBanco().emit(self.registro())
        self.assertEqual(len(gravados), 2)

    def test_grava_em_outra_thread(self):
        gravados = []
        with patch('application.erros.services.registrar_erro', side_effect=gravados.append):
            linha = threading.Thread(target=GuardarErroNoBanco().emit, args=(self.registro(),))
            linha.start()
            linha.join()
        self.assertEqual(len(gravados), 1)


class FormatacaoDetalhesTest(SimpleTestCase):

    def test_zero_negativo_vira_zero(self):
        self.assertEqual(numero('-0.0004'), '0')

    def test_unidade_em_branco_conta_como_unidade(self):
        self.assertEqual(item(2, '', 'Pão'), '2× Pão')

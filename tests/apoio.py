import base64
import dataclasses
import importlib
import io
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from infrastructure.utils.supabase_storage import SupabaseAPIError

def dataclasses_do_pacote(pacote):
    """Dataclasses definidas em `pacote` (fora testes e migrações). Acha os módulos pelos arquivos .py, então uma
    pasta sem __init__.py também entra (o pkgutil.walk_packages pularia a pasta inteira)."""
    raiz = Path(pacote.__path__[0])
    classes = set()
    for arquivo in sorted(raiz.rglob('*.py')):
        partes = arquivo.relative_to(raiz.parent).with_suffix('').parts
        if 'tests' in partes or 'migrations' in partes:
            continue
        nome = '.'.join(partes[:-1] if partes[-1] == '__init__' else partes)
        modulo = importlib.import_module(nome)
        classes |= {objeto for objeto in vars(modulo).values() if isinstance(objeto, type)
                    and dataclasses.is_dataclass(objeto) and objeto.__module__ == nome}
    return classes


URL_PUBLICA = "https://exemplo.supabase.co/storage/v1/object/public/imagens"


def imagem_de_teste(nome='foto.png', formato='PNG'):
    """Arquivo de imagem real (2x2 px), aceito pela validação do Pillow."""
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2), 'red').save(buffer, formato)
    content_type = Image.MIME[formato]
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type=content_type)


# Foto HEIC de verdade (64x48 px, vermelha), como as do iPhone: gerada uma vez com o pillow-heif.
_FOTO_HEIC = (
    'AAAAHGZ0eXBoZWljAAAAAG1pZjFoZWljbWlhZgAAAX1tZXRhAAAAAAAAACFoZGxyAAAAAAAAAABwaWN0AAAAAAAAAAAAAAAAAAAA'
    'ACJpbG9jAAAAAERAAAEAAQAAAAABoQABAAAAAAAAAB0AAAAjaWluZgAAAAAAAQAAABVpbmZlAgAAAAABAABodmMxAAAAAA5waXRt'
    'AAAAAAABAAAA/WlwcnAAAADdaXBjbwAAAHZodmNDAQNwAAAAAAAAAAAAHvAA/P34+AAADwNgAAEAGEABDAH//wNwAAADAJAAAAMA'
    'AAMAHroCQGEAAQAqQgEBA3AAAAMAkAAAAwAAAwAeoCCBBZbq5Ka5uAhoMCAAAAMDIAAAAwAhYgABAAZEAcFzwIkAAAATY29scm5j'
    'bHgAAQANAAaAAAAAFGlzcGUAAAAAAAAAQAAAAEAAAAAoY2xhcAAAAEAAAAABAAAAMAAAAAEAAAAAAAAAAv////AAAAACAAAAEHBp'
    'eGkAAAAAAwgICAAAABhpcG1hAAAAAAAAAAEAAQWBAgMFhAAAACVtZGF0AAAAGSgBrxOA9SeBP//gpUf/utZ4fg8Lfnny1PA='
)


def foto_heic_de_teste(nome='foto.heic'):
    return SimpleUploadedFile(nome, base64.b64decode(_FOTO_HEIC), content_type='image/heic')


class StorageFalso:
    """Dublê do SupabaseStorage que registra chamadas e pode falhar no N-ésimo envio."""

    def __init__(self, falhar_no_envio=None):
        self.enviados = []
        self.removidos = []
        self._falhar_no_envio = falhar_no_envio

    def enviar(self, arquivo, pasta):
        if len(self.enviados) == self._falhar_no_envio:
            raise SupabaseAPIError("storage fora do ar")
        url = f"{URL_PUBLICA}/{pasta}/{arquivo.name}"
        self.enviados.append(url)
        return url

    def remover(self, url_publica):
        self.removidos.append(url_publica)


def garantir_planos_iniciais():
    """Cria os planos iniciais pela mesma função da migração 0015 (não duplica se já existirem).

    O teste de migração (TransactionTestCase) esvazia o banco quando termina, planos inclusive: sem isto,
    os testes de planos passariam ou falhariam conforme a ordem em que rodam.
    """
    from importlib import import_module
    from django.apps import apps
    import_module('infrastructure.migrations.0015_planos_iniciais').criar_planos(apps, None)


class ComPlanosIniciais:
    """Mistura para TestCase: os planos iniciais existem em todo teste, qualquer que seja a ordem."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        garantir_planos_iniciais()


class CenarioDeLoja:
    """Monta dados de uma loja para testes de relatórios, com datas no fuso local."""

    def __init__(self, nome_loja="Loja Teste"):
        from infrastructure.models import LojaModel
        self.loja = LojaModel.objects.create(nome_loja=nome_loja)

    @staticmethod
    def quando(ano, mes, dia, hora=12, minuto=0):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime(ano, mes, dia, hora, minuto, tzinfo=ZoneInfo('America/Sao_Paulo'))

    def produto(self, nome, preco_venda='10.00', preco_custo='0.00', estoque=10, categoria='', **extras):
        from decimal import Decimal
        from infrastructure.models import Produto
        return Produto.objects.create(
            loja=self.loja, nome=nome, categoria=categoria, quantidade_estoque=estoque,
            preco_venda=Decimal(preco_venda), preco_custo=Decimal(preco_custo), **extras,
        )

    def cliente(self, nome):
        from infrastructure.models import Cliente
        return Cliente.objects.create(loja=self.loja, nome=nome)

    def venda(self, quando, itens, cliente=None):
        """`itens`: lista de (produto, quantidade[, preço unitário]). O total é a soma dos itens."""
        from decimal import Decimal
        from infrastructure.models import ItemVenda, Venda
        linhas = []
        for produto, quantidade, *preco in itens:
            linhas.append((produto, quantidade, Decimal(preco[0]) if preco else produto.preco_venda))
        venda = Venda.objects.create(
            loja=self.loja, cliente=cliente, data_venda=quando,
            valor_total=sum((q * preco for _, q, preco in linhas), Decimal('0.00')),
        )
        for produto, quantidade, preco in linhas:
            ItemVenda.objects.create(
                venda=venda, produto=produto, quantidade=quantidade, preco_unitario=preco, custo_unitario=produto.preco_custo,
            )
        return venda

    def pagamento(self, cliente, valor, quando):
        from decimal import Decimal
        from infrastructure.models import PagamentoCliente
        pagamento = PagamentoCliente.objects.create(loja=self.loja, cliente=cliente, valor=Decimal(valor))
        PagamentoCliente.objects.filter(pk=pagamento.pk).update(data_pagamento=quando)  # auto_now_add
        return pagamento

    def usuario(self):
        from types import SimpleNamespace
        return SimpleNamespace(is_superuser=False, loja=self.loja)


class MercadoPagoFalso:
    """Dublê do cliente do Mercado Pago: gera Pix de mentira e responde consultas com o que o teste mandar."""

    def __init__(self, erro_ao_criar=None):
        self.pix_criados = []
        self.consultas = []
        self.pagamentos = {}
        self._erro_ao_criar = erro_ao_criar

    def criar_pix(self, *, valor, descricao, email, referencia, expira_em):
        from infrastructure.pagamentos.mercado_pago import PixGerado
        if self._erro_ao_criar:
            raise self._erro_ao_criar
        self.pix_criados.append({'valor': valor, 'descricao': descricao, 'email': email, 'referencia': referencia, 'expira_em': expira_em})
        pagamento_id = str(1000 + len(self.pix_criados))
        return PixGerado(pagamento_id, f"000201PIX{pagamento_id}", "iVBORw0KGgo=")

    def aprovar(self, cobranca, **diferencas):
        """Faz o pagamento da cobrança aparecer como aprovado (com diferenças, para simular fraude/erro)."""
        self.responder(cobranca, status='approved', **diferencas)

    def responder(self, cobranca, *, status, **diferencas):
        from infrastructure.pagamentos.mercado_pago import PagamentoConsultado
        dados = {'pagamento_id': cobranca.pagamento_id, 'status': status, 'valor': cobranca.valor,
                 'moeda': 'BRL', 'referencia': str(cobranca.referencia), **diferencas}
        self.pagamentos[cobranca.pagamento_id] = PagamentoConsultado(**dados)

    def consultar(self, pagamento_id):
        from infrastructure.pagamentos.mercado_pago import PagamentoConsultado
        self.consultas.append(pagamento_id)
        return self.pagamentos.get(pagamento_id) or PagamentoConsultado(pagamento_id, 'pending', None, 'BRL', '')


class BackupsFalsos:
    """No lugar do bucket `backups` do Supabase: guarda os arquivos enviados na memória."""

    def __init__(self, falhar_no_envio=False, falhar_ao_remover=()):
        self.arquivos = {}
        self.removidos = []
        self._falhar_no_envio = falhar_no_envio
        self._falhar_ao_remover = falhar_ao_remover

    def enviar(self, caminho_local, nome):
        if self._falhar_no_envio:
            raise SupabaseAPIError("Supabase fora do ar")
        with open(caminho_local, 'rb') as arquivo:
            self.arquivos[nome] = arquivo.read()

    def baixar(self, nome, destino):
        destino.write(self.arquivos[nome])

    def remover(self, nome):
        if nome in self._falhar_ao_remover:
            raise SupabaseAPIError("não removeu")
        self.removidos.append(nome)
        self.arquivos.pop(nome, None)

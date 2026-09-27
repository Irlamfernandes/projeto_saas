import io
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from infrastructure.utils.supabase_storage import SupabaseAPIError

URL_PUBLICA = "https://exemplo.supabase.co/storage/v1/object/public/imagens"


def imagem_de_teste(nome='foto.png', formato='PNG'):
    """Arquivo de imagem real (2x2 px), aceito pela validação do Pillow."""
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2), 'red').save(buffer, formato)
    content_type = Image.MIME[formato]
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type=content_type)


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

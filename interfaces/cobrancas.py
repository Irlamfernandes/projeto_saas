"""Mensagem de cobrança pronta para o WhatsApp: o dono confere e toca em enviar (nada é mandado sozinho)."""
import re
from dataclasses import dataclass
from urllib.parse import quote
from django.utils import timezone
from application.vendas.pendencias import Situacao
from infrastructure.utils.formatacao import item as descrever_item, reais


@dataclass(frozen=True)
class CobrancaNaTela:
    cobranca: object  # ClienteACobrar
    mensagem: str
    link: str  # vazio se o cliente não tem telefone que sirva no WhatsApp


def numero_do_whatsapp(telefone):
    """Só os dígitos, com o 55 do Brasil na frente. Vazio se não tiver jeito de telefone com DDD."""
    digitos = re.sub(r'\D', '', telefone or '')
    if len(digitos) in (10, 11):
        return f"55{digitos}"
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        return digitos
    return ''


def link_do_whatsapp(telefone, texto):
    numero = numero_do_whatsapp(telefone)
    return f"https://wa.me/{numero}?text={quote(texto)}" if numero else ''


def _quando(pendencia, hoje):
    situacao = pendencia.situacao(hoje)
    if situacao == Situacao.ATRASADA:
        return f"venceu em {pendencia.vencimento:%d/%m}"
    if situacao == Situacao.VENCE_HOJE:
        return "vence hoje"
    return f"vence em {pendencia.vencimento:%d/%m}"


def _linha(pendencia, hoje):
    venda = pendencia.venda
    itens = ", ".join(descrever_item(i.quantidade, i.produto.unidade, i.produto.nome) for i in venda.itens.all())
    return f"• Compra de {timezone.localtime(venda.data_venda):%d/%m} ({itens}): {_quando(pendencia, hoje)} · {reais(pendencia.pendente)}"


def mensagem_de_cobranca(cobranca):
    cliente = cobranca.cliente
    return "\n".join([
        f"Olá, {cliente.nome}! Aqui é da {cliente.loja.nome_loja}.",
        "Passando para lembrar do pagamento combinado:",
        "",
        *(_linha(pendencia, cobranca.hoje) for pendencia in cobranca.pendencias),
        "",
        f"Total: {reais(cobranca.total)}",
        "Se já pagou, pode desconsiderar esta mensagem. Obrigado!",
    ])


def cobrancas_na_tela(cobrancas):
    telas = []
    for cobranca in cobrancas:
        mensagem = mensagem_de_cobranca(cobranca)
        telas.append(CobrancaNaTela(cobranca, mensagem, link_do_whatsapp(cobranca.cliente.telefone, mensagem)))
    return telas

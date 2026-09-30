"""Tira e-mails e números longos (telefone, CPF, cartão) de textos que saem do alcance da loja: o log do
Render e a tela "Erros do sistema" do admin. A mensagem de um erro pode trazer o dado que o causou
(ex.: "Key (telefone)=(24999998888) already exists").
"""
import re

EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
# 8 ou mais dígitos, com ou sem espaço, ponto, hífen, barra e parênteses no meio: (24) 99999-8888, 123.456.789-00.
NUMERO_LONGO = re.compile(r'\+?\(?(?:\d[\s().\-/]*){7,}\d')
# Datas (2026-09-29, 2026-09-29 10:00) também são 8 dígitos seguidos, mas não são dado pessoal e ajudam a ler o erro.
DATA = re.compile(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2})?')


def _numero(encontrado):
    trecho = encontrado.group()
    return trecho if DATA.fullmatch(trecho) else '[número]'


def mascarar(texto):
    return NUMERO_LONGO.sub(_numero, EMAIL.sub('[e-mail]', texto or ''))

"""Tira e-mails e números longos (telefone, CPF, cartão) de textos que saem do alcance da loja: o log do
Render e a tela "Erros do sistema" do admin. A mensagem de um erro pode trazer o dado que o causou
(ex.: "Key (telefone)=(24999998888) already exists").
"""
import re

# Quantificadores possessivos (++) e o início preso ao começo da palavra: o texto é lido uma vez só, sem voltar atrás
# (um erro com um texto enorme não trava o registro).
EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]++@[\w-]++(?:\.[\w-]++)+')
# Um trecho de dígitos com espaço, ponto, hífen, barra e parênteses no meio: (24) 99999-8888, 123.456.789-00.
TRECHO_NUMERICO = re.compile(r'\+?\(?\d[\d\s().\-/]*+')
DIGITOS_DE_UM_NUMERO_LONGO = 8
# Datas (2026-09-29, 2026-09-29 10:00) também são 8 dígitos seguidos, mas não são dado pessoal e ajudam a ler o erro.
DATA = re.compile(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2})?')


def _numero(encontrado):
    trecho = encontrado.group()
    fim = len(trecho.rstrip(' ().-/\t\n\r\f\v'))  # o número vai até o último dígito; o que sobra fica no texto
    numero, resto = trecho[:fim], trecho[fim:]
    if sum(c.isdigit() for c in numero) < DIGITOS_DE_UM_NUMERO_LONGO or DATA.fullmatch(numero):
        return trecho
    return '[número]' + resto


def mascarar(texto):
    return TRECHO_NUMERICO.sub(_numero, EMAIL.sub('[e-mail]', texto or ''))

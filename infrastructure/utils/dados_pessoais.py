"""Tira e-mails e números longos (telefone, CPF, cartão) de textos que saem do alcance da loja: o log do
Render e a tela "Erros do sistema" do admin. A mensagem de um erro pode trazer o dado que o causou
(ex.: "Key (telefone)=(24999998888) already exists").
"""
import re

# A busca começa no @ e o nome antes dele é lido de trás para frente: o texto é lido uma vez só, sem voltar atrás
# (um erro com um texto enorme não trava o registro).
DOMINIO = re.compile(r'@[\w-]++(?:\.[\w-]++)+')
LETRA_DO_NOME = re.compile(r'[\w.+-]')
# Um trecho de dígitos com espaço, ponto, hífen, barra e parênteses no meio: (24) 99999-8888, 123.456.789-00.
TRECHO_NUMERICO = re.compile(r'\+?\(?\d[\d\s().\-/]*+')
DIGITOS_DE_UM_NUMERO_LONGO = 8
# Datas (2026-09-29, 2026-09-29 10:00) também são 8 dígitos seguidos, mas não são dado pessoal e ajudam a ler o erro.
DATA = re.compile(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2})?')


def _numero(encontrado):
    trecho = encontrado.group()
    # O número vai até o último dígito; o que sobra (espaço, parêntese, hífen) fica no texto.
    fim = max(posicao for posicao, letra in enumerate(trecho) if letra.isdigit()) + 1
    numero, resto = trecho[:fim], trecho[fim:]
    if sum(c.isdigit() for c in numero) < DIGITOS_DE_UM_NUMERO_LONGO or DATA.fullmatch(numero):
        return trecho
    return '[número]' + resto


def _sem_emails(texto):
    partes, inicio = [], 0
    for dominio in DOMINIO.finditer(texto):
        comeco = dominio.start()
        while comeco > inicio and LETRA_DO_NOME.fullmatch(texto[comeco - 1]):
            comeco -= 1
        if comeco < dominio.start():  # "@loja.com" sem nome antes não é e-mail
            partes += [texto[inicio:comeco], '[e-mail]']
            inicio = dominio.end()
    return ''.join(partes) + texto[inicio:]


def mascarar(texto):
    return TRECHO_NUMERICO.sub(_numero, _sem_emails(texto or ''))

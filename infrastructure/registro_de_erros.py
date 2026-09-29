"""Liga o logging do Python à tela "Erros do sistema" do admin (configurado em LOGGING, config/settings.py).

Todo registro de nível ERROR — a página que quebrou (erro 500) e os `logger.exception` do próprio código —
vira uma linha na tabela, além de ir para o console (o log do Render). Nunca guarda o que foi digitado
nos formulários nem os parâmetros do endereço: só o tipo do erro, a mensagem, o ponto do código e a tela.
"""
import logging
import threading
import traceback
from pathlib import Path
from django.conf import settings
from infrastructure.utils.dados_pessoais import mascarar

RAIZ = Path(settings.BASE_DIR)
PASTAS_DE_TERCEIROS = ('site-packages', 'dist-packages')  # bibliotecas instaladas, mesmo dentro do venv do projeto


def _do_projeto(arquivo):
    return arquivo.startswith(str(RAIZ)) and not any(pasta in arquivo for pasta in PASTAS_DE_TERCEIROS)


def _relativo(arquivo):
    return str(Path(arquivo).relative_to(RAIZ)) if _do_projeto(arquivo) else Path(arquivo).name


def _local_da_excecao(tb):
    """O último ponto do NOSSO código por onde o erro passou (e não o de dentro do Django ou de uma biblioteca)."""
    quadros = traceback.extract_tb(tb)
    nossos = [quadro for quadro in quadros if _do_projeto(quadro.filename)]
    quadro = (nossos or quadros)[-1]
    return f"{_relativo(quadro.filename)}:{quadro.lineno} em {quadro.name}"


def _tipo(excecao):
    classe = type(excecao)
    return classe.__qualname__ if classe.__module__ == 'builtins' else f"{classe.__module__}.{classe.__qualname__}"


def _quem(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return None, None
    return getattr(usuario, 'loja_id', None), usuario.pk


def ocorrencia_do_registro(record):
    from application.erros.services import Ocorrencia

    request = getattr(record, 'request', None)
    loja_id, usuario_id = _quem(request) if request is not None else (None, None)
    tela = {
        'caminho': getattr(request, 'path', ''), 'metodo': getattr(request, 'method', ''),
        'loja_id': loja_id, 'usuario_id': usuario_id,
    }
    if record.exc_info and record.exc_info[1] is not None:
        _, excecao, tb = record.exc_info
        return Ocorrencia(
            tipo=_tipo(excecao), mensagem=str(excecao), local=_local_da_excecao(tb),
            detalhes=''.join(traceback.format_exception(excecao)), **tela,
        )
    return Ocorrencia(
        tipo=record.name, mensagem=record.getMessage(), local=f"{_relativo(record.pathname)}:{record.lineno}", **tela,
    )


class GuardarErroNoBanco(logging.Handler):
    """Grava o erro na tabela. Se a própria gravação falhar (ex.: banco fora do ar), o erro segue só no console."""

    _gravando = threading.local()

    def emit(self, record):
        if getattr(self._gravando, 'ativo', False):  # um erro ao gravar o erro não pode virar um laço
            return
        self._gravando.ativo = True
        try:
            from application.erros.services import registrar_erro
            registrar_erro(ocorrencia_do_registro(record))
        except Exception:  # noqa: BLE001 - registrar o erro nunca pode derrubar a página
            self.handleError(record)
        finally:
            self._gravando.ativo = False


class SemDadosPessoais(logging.Formatter):
    """Formato do console (log do Render): o mesmo texto de sempre, com e-mails e telefones mascarados."""

    def format(self, record):
        return mascarar(super().format(record))


class SemAvisosDeSeguranca(logging.Filter):
    """Os avisos de `django.security` (ex.: robô chamando o site com outro endereço) ficam só no console:
    são ruído na tela de erros, não defeito do sistema."""

    def filter(self, record):
        return not record.name.startswith('django.security')

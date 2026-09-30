"""Guarda os erros inesperados de produção para a tela "Erros do sistema" do admin."""
import hashlib
from dataclasses import dataclass
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from infrastructure.models import ErroDoSistema
from infrastructure.utils.dados_pessoais import mascarar

LIMITE_DA_MENSAGEM = 1000
LIMITE_DOS_DETALHES = 20000


@dataclass(frozen=True)
class Ocorrencia:
    tipo: str
    mensagem: str = ''
    local: str = ''
    detalhes: str = ''
    caminho: str = ''
    metodo: str = ''
    loja_id: int | None = None
    usuario_id: int | None = None

    @property
    def assinatura(self):
        """O que identifica "o mesmo erro": tipo e ponto do código. Sem ponto conhecido, a própria mensagem."""
        chave = f"{self.tipo}|{self.local or self.mensagem}"
        return hashlib.sha256(chave.encode()).hexdigest()


def registrar_erro(ocorrencia, agora=None):
    """Soma no erro em aberto com a mesma assinatura ou abre um novo. Devolve o registro."""
    agora = agora or timezone.now()
    ultima = {
        # A mensagem do erro pode trazer o dado que o causou (telefone, e-mail): o admin não precisa vê-lo.
        'mensagem': mascarar(ocorrencia.mensagem)[:LIMITE_DA_MENSAGEM],
        'detalhes': mascarar(ocorrencia.detalhes)[-LIMITE_DOS_DETALHES:],  # o fim do traceback é onde o erro aconteceu
        'caminho': ocorrencia.caminho[:500],
        'metodo': ocorrencia.metodo[:10],
        'loja_id': ocorrencia.loja_id,
        'usuario_id': ocorrencia.usuario_id,
        'ultima_vez': agora,
    }
    with transaction.atomic():
        aberto = (
            ErroDoSistema.objects.select_for_update()
            .filter(assinatura=ocorrencia.assinatura, resolvido=False).first()
        )
        if aberto:
            ErroDoSistema.objects.filter(pk=aberto.pk).update(ocorrencias=F('ocorrencias') + 1, **ultima)
            aberto.refresh_from_db()
            return aberto
        return ErroDoSistema.objects.create(
            assinatura=ocorrencia.assinatura, tipo=ocorrencia.tipo[:200], local=ocorrencia.local[:300],
            primeira_vez=agora, **ultima,
        )

import logging
import mimetypes
import uuid
from pathlib import PurePath
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Falha ao acessar o armazenamento de arquivos."""


class SupabaseConfigError(StorageError):
    """Credenciais do Supabase ausentes."""


class SupabaseAPIError(StorageError):
    """Erro na comunicação com a API do Supabase."""


def gerar_nome_unico(nome_original):
    """Nome aleatório que preserva só a extensão: evita sobrescrita e caracteres perigosos na URL."""
    extensao = PurePath(nome_original or '').suffix.lower()
    if not extensao[1:].isalnum():
        extensao = ''
    return f"{uuid.uuid4().hex}{extensao}"


class SupabaseStorage:
    BUCKET = 'imagens'
    TIMEOUT_SEGUNDOS = 10

    def __init__(self, url, chave):
        self._base_url = self._normalizar_base_url(url)
        self._chave = chave

    @classmethod
    def from_settings(cls):
        return cls(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def enviar(self, arquivo, pasta):
        """Envia o arquivo para `<pasta>/<nome único>` e retorna sua URL pública."""
        self._exigir_configuracao()
        caminho = f"{pasta}/{gerar_nome_unico(arquivo.name)}"
        content_type = mimetypes.guess_type(caminho)[0] or 'application/octet-stream'

        try:
            resposta = requests.post(
                self._url_objeto(caminho),
                data=arquivo.read(),
                headers={**self._headers(), 'Content-Type': content_type},
                timeout=self.TIMEOUT_SEGUNDOS,
            )
        except requests.RequestException as erro:
            raise SupabaseAPIError(f"Erro de comunicação com o Supabase Storage: {erro}") from erro

        if resposta.status_code not in (200, 201):
            raise SupabaseAPIError(f"Erro na API do Supabase ({resposta.status_code}): {resposta.text}")
        return f"{self._base_url}/storage/v1/object/public/{self.BUCKET}/{caminho}"

    def remover(self, url_publica):
        """Remove o arquivo da URL pública. Melhor esforço: falhas são registradas, nunca propagadas."""
        caminho = self._caminho_da_url(url_publica)
        if caminho is None or not self._configurado():
            return

        try:
            resposta = requests.delete(
                self._url_objeto(caminho), headers=self._headers(), timeout=self.TIMEOUT_SEGUNDOS,
            )
        except requests.RequestException:
            logger.warning("Falha ao remover imagem %s do Supabase", caminho, exc_info=True)
            return

        if resposta.status_code not in (200, 204):
            logger.warning("Supabase recusou remover %s (%s)", caminho, resposta.status_code)

    def baixar(self, url_publica):
        """Conteúdo de um arquivo deste bucket, ou None. Recusa URLs de fora (o servidor não busca endereços quaisquer)."""
        prefixo = f"{self._base_url}/storage/v1/object/public/{self.BUCKET}/"
        if not self._base_url or not (url_publica or '').startswith(prefixo) or url_publica == prefixo:
            return None
        try:
            resposta = requests.get(url_publica, timeout=self.TIMEOUT_SEGUNDOS)
        except requests.RequestException:
            logger.warning("Falha ao baixar %s do Supabase", url_publica, exc_info=True)
            return None
        return resposta.content if resposta.status_code == 200 else None

    def _configurado(self):
        return bool(self._base_url and self._chave)

    def _exigir_configuracao(self):
        if not self._configurado():
            raise SupabaseConfigError("Credenciais do Supabase não configuradas no .env.")

    def _headers(self):
        return {'apikey': self._chave, 'Authorization': f"Bearer {self._chave}"}

    def _url_objeto(self, caminho):
        return f"{self._base_url}/storage/v1/object/{self.BUCKET}/{caminho}"

    def _caminho_da_url(self, url_publica):
        prefixo = f"/storage/v1/object/public/{self.BUCKET}/"
        _, encontrado, caminho = (url_publica or '').partition(prefixo)
        return caminho if encontrado and caminho else None

    @staticmethod
    def _normalizar_base_url(url):
        base = (url or '').strip().rstrip('/')
        return base.removesuffix('/rest/v1')

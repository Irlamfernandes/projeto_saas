"""Bucket PRIVADO `backups` no Supabase Storage (o `imagens` das fotos é público; este nunca).

Precisa da chave secreta do Supabase (sb_secret / service_role) em SUPABASE_KEY: é ela que lê bucket privado.
"""
import requests
from django.conf import settings
from infrastructure.utils.supabase_storage import SupabaseAPIError, SupabaseConfigError, SupabaseStorage

BLOCO = 1024 * 1024


class BackupsNoSupabase:
    BUCKET = 'backups'
    TIMEOUT_SEGUNDOS = 120

    def __init__(self, url, chave):
        self._base_url = SupabaseStorage._normalizar_base_url(url)
        self._chave = chave

    @classmethod
    def from_settings(cls):
        return cls(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def enviar(self, caminho_local, nome):
        self._garantir_bucket()
        with open(caminho_local, 'rb') as arquivo:
            self._pedir('post', f"object/{self.BUCKET}/{nome}", data=arquivo,
                        headers={'Content-Type': 'application/octet-stream'})

    def baixar(self, nome, destino):
        """Escreve o arquivo em `destino` (aberto em binário) aos poucos, sem carregar tudo na memória."""
        resposta = self._pedir('get', f"object/{self.BUCKET}/{nome}", stream=True)
        for bloco in resposta.iter_content(BLOCO):
            destino.write(bloco)

    def remover(self, nome):
        self._pedir('delete', f"object/{self.BUCKET}/{nome}")

    def _garantir_bucket(self):
        """Cria o bucket privado na primeira vez; se alguém o deixou público, recusa guardar backup nele."""
        existente = self._pedir('get', f"bucket/{self.BUCKET}", aceitar=(200, 400, 404))
        if existente.status_code != 200:
            self._pedir('post', 'bucket', json={'id': self.BUCKET, 'name': self.BUCKET, 'public': False})
        elif existente.json().get('public'):
            raise SupabaseAPIError(f"O bucket '{self.BUCKET}' está público no Supabase: deixe-o privado antes do backup.")

    def _pedir(self, metodo, caminho, aceitar=(200, 201), headers=None, **opcoes):
        if not (self._base_url and self._chave):
            raise SupabaseConfigError("Credenciais do Supabase não configuradas.")
        try:
            resposta = requests.request(
                metodo, f"{self._base_url}/storage/v1/{caminho}", timeout=self.TIMEOUT_SEGUNDOS,
                headers={'apikey': self._chave, 'Authorization': f"Bearer {self._chave}", **(headers or {})}, **opcoes,
            )
        except requests.RequestException as erro:
            raise SupabaseAPIError(f"Erro de comunicação com o Supabase Storage: {erro}") from erro
        if resposta.status_code not in aceitar:
            raise SupabaseAPIError(f"Erro na API do Supabase ({resposta.status_code}): {resposta.text[:300]}")
        return resposta

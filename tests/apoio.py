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

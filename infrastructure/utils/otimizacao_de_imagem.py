"""Deixa as fotos leves antes de guardar: reduz o tamanho (downscaling) e regrava em WebP com perda."""
from io import BytesIO
from pathlib import PurePath
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

LADO_MAXIMO = 1024  # px no maior lado: nítido na tela do celular e na galeria ampliada
QUALIDADE_WEBP = 70  # 0–100: foto de ~25 KB; acima disso o arquivo cresce muito sem ganho visível na tela


class ImagemIlegivel(Exception):
    """O arquivo não pôde ser lido como imagem."""


def otimizar_imagem(arquivo, lado_maximo=LADO_MAXIMO, qualidade=QUALIDADE_WEBP):
    """Retorna a foto em WebP com no máximo `lado_maximo` px no maior lado.

    - endireita fotos de celular (rotação do EXIF) e descarta os metadados, inclusive a localização GPS;
    - só reduz: imagem menor que o limite mantém o tamanho;
    - preserva a transparência de PNGs.
    """
    try:
        with Image.open(arquivo) as original:  # o Pillow volta ao início do arquivo sozinho
            # JPEG: decodifica já reduzido (1/2, 1/4, 1/8), sem abrir a foto inteira na memória.
            original.draft(None, (lado_maximo, lado_maximo))
            imagem = ImageOps.exif_transpose(original)
            imagem = imagem.convert('RGBA' if _tem_transparencia(imagem) else 'RGB')
            imagem.thumbnail((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
            saida = BytesIO()
            imagem.save(saida, format='WEBP', quality=qualidade)
    except (OSError, ValueError, Image.DecompressionBombError) as erro:
        raise ImagemIlegivel(f"Não foi possível ler a imagem '{arquivo.name}'.") from erro

    return ContentFile(saida.getvalue(), name=f"{PurePath(arquivo.name).stem}.webp")


def _tem_transparencia(imagem):
    return imagem.mode in ('RGBA', 'LA', 'PA') or 'transparency' in imagem.info

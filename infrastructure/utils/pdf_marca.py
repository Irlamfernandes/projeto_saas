"""Cabeçalho dos PDFs: marca (logotipo) e nome da loja."""
import io
import logging
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle
from infrastructure.utils.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)

LADO_DA_MARCA = 48  # pt (~1,7 cm) no maior lado
_ESTILOS = getSampleStyleSheet()
ESTILO_NOME = ParagraphStyle(
    'NomeDaLoja', parent=_ESTILOS['Heading1'], fontSize=16, textColor=colors.HexColor('#1f2937'), spaceAfter=2,
)
ESTILO_SUBTITULO = ParagraphStyle(
    'SubtituloDoPdf', parent=_ESTILOS['Normal'], fontSize=10, textColor=colors.HexColor('#4b5563'), spaceAfter=15,
)


def cabecalho_da_loja(loja, subtitulo, storage=None):
    """Nome da loja e subtítulo; com a marca à esquerda quando a loja tiver uma que dê para ler."""
    textos = [Paragraph(f"<b>{escape(loja.nome_loja)}</b>", ESTILO_NOME), Paragraph(escape(subtitulo), ESTILO_SUBTITULO)]
    marca = marca_da_loja(loja, storage)
    if marca is None:
        return textos
    tabela = Table([[marca, textos]], colWidths=[LADO_DA_MARCA + 12, None], hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [tabela, Spacer(1, ESTILO_SUBTITULO.spaceAfter)]


def marca_da_loja(loja, storage=None):
    """Imagem da marca proporcional em até LADO_DA_MARCA, ou None. Falhas nunca impedem o PDF de sair."""
    if not loja.logo_url:
        return None
    conteudo = (storage or SupabaseStorage.from_settings()).baixar(loja.logo_url)
    if not conteudo:
        return None
    try:
        largura, altura = ImageReader(io.BytesIO(conteudo)).getSize()
    except Exception:  # o reportlab embrulha erros do Pillow em tipos variados
        logger.warning("Marca da loja %s ilegível para o PDF", loja.pk, exc_info=True)
        return None
    escala = LADO_DA_MARCA / max(largura, altura)
    return Image(io.BytesIO(conteudo), width=largura * escala, height=altura * escala)

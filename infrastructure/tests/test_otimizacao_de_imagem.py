import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from infrastructure.utils.otimizacao_de_imagem import LADO_MAXIMO, ImagemIlegivel, otimizar_imagem
from tests.apoio import foto_heic_de_teste

TAG_ORIENTACAO = 0x0112
TAG_GPS = 0x8825
GIRADA_90_GRAUS = 6


def _foto(tamanho, formato='JPEG', modo='RGB', nome=None, exif=None, **opcoes):
    """Imagem com degradê (parece uma foto: comprime como uma, ao contrário de uma cor lisa)."""
    imagem = Image.linear_gradient('L').resize(tamanho).convert(modo)
    if modo == 'RGBA':
        imagem.putalpha(Image.new('L', tamanho, 0))
    buffer = io.BytesIO()
    if exif is not None:
        opcoes['exif'] = exif
    imagem.save(buffer, formato, **opcoes)
    return SimpleUploadedFile(nome or f"foto.{formato.lower()}", buffer.getvalue())


def _abrir(arquivo):
    return Image.open(io.BytesIO(arquivo.read()))


class OtimizarImagemTest(SimpleTestCase):

    def test_le_foto_heic_do_iphone(self):
        otimizada = otimizar_imagem(foto_heic_de_teste())
        self.assertEqual(otimizada.name, 'foto.webp')
        self.assertEqual(_abrir(otimizada).size, (64, 48))

    def test_reduz_o_maior_lado_mantendo_a_proporcao(self):
        imagem = _abrir(otimizar_imagem(_foto((4000, 3000))))
        self.assertEqual(imagem.size, (LADO_MAXIMO, LADO_MAXIMO * 3 // 4))

    def test_foto_em_pe_limita_a_altura(self):
        imagem = _abrir(otimizar_imagem(_foto((1500, 3000), 'PNG')))
        self.assertEqual(imagem.size, (LADO_MAXIMO // 2, LADO_MAXIMO))

    def test_nao_amplia_imagem_pequena(self):
        imagem = _abrir(otimizar_imagem(_foto((300, 200))))
        self.assertEqual(imagem.size, (300, 200))

    def test_regrava_em_webp_com_o_mesmo_nome(self):
        otimizada = otimizar_imagem(_foto((50, 50), 'PNG', nome='Bolo de Cenoura.png'))
        self.assertEqual(otimizada.name, 'Bolo de Cenoura.webp')
        self.assertEqual(_abrir(otimizada).format, 'WEBP')

    def test_fica_bem_menor_que_a_foto_original(self):
        original = _foto((4000, 3000), quality=95)
        otimizada = otimizar_imagem(original)
        self.assertLess(otimizada.size, original.size / 10)

    def test_endireita_foto_girada_pelo_celular(self):
        exif = Image.Exif()
        exif[TAG_ORIENTACAO] = GIRADA_90_GRAUS
        imagem = _abrir(otimizar_imagem(_foto((400, 200), exif=exif)))
        self.assertEqual(imagem.size, (200, 400))

    def test_descarta_metadados_como_a_localizacao(self):
        exif = Image.Exif()
        exif[TAG_GPS] = {1: 'S', 2: (23.0, 32.0, 0.0)}
        imagem = _abrir(otimizar_imagem(_foto((100, 100), exif=exif)))
        self.assertEqual(len(imagem.getexif()), 0)

    def test_mantem_a_transparencia_de_png(self):
        imagem = _abrir(otimizar_imagem(_foto((50, 50), 'PNG', modo='RGBA')))
        self.assertEqual(imagem.mode, 'RGBA')

    def test_sem_transparencia_grava_em_rgb(self):
        imagem = _abrir(otimizar_imagem(_foto((50, 50), 'PNG')))
        self.assertEqual(imagem.mode, 'RGB')

    def test_le_desde_o_inicio_mesmo_se_o_arquivo_ja_foi_lido(self):
        foto = _foto((50, 50))
        foto.read()
        self.assertEqual(_abrir(otimizar_imagem(foto)).size, (50, 50))

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        falso = SimpleUploadedFile('virus.png', b'<script>alert(1)</script>')
        with self.assertRaisesMessage(ImagemIlegivel, "Não foi possível ler a imagem 'virus.png'."):
            otimizar_imagem(falso)

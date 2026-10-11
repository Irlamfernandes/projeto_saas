/* Antes de enviar, o navegador reduz cada foto para no máximo 1600 px no maior lado. Foto de câmera de 50 a 200
   megapixels vira algumas centenas de KB: o envio pelo 4G fica rápido e o servidor não recusa por tamanho.
   PNG continua PNG (pode ter fundo transparente); o resto vira JPEG. O que o navegador não consegue ler (HEIC no
   Chrome, por exemplo) segue como veio: o servidor converte. */
const LADO_MAXIMO = 1600;
const QUALIDADE = 0.85;
const PNG = 'image/png';

function medidasReduzidas(largura, altura, lado = LADO_MAXIMO) {
    const escala = Math.min(1, lado / Math.max(largura, altura));
    return { largura: Math.round(largura * escala), altura: Math.round(altura * escala) };
}

function nomeEmJpeg(nome) {
    const ponto = nome.lastIndexOf('.');
    return `${ponto > 0 ? nome.slice(0, ponto) : nome}.jpg`;
}

async function reduzirFoto(arquivo, ambiente) {
    const bitmap = await ambiente.criarBitmap(arquivo);
    if (Math.max(bitmap.width, bitmap.height) <= LADO_MAXIMO) return arquivo; // já é pequena: segue como veio
    const { largura, altura } = medidasReduzidas(bitmap.width, bitmap.height);
    const canvas = ambiente.criarCanvas(largura, altura);
    canvas.getContext('2d').drawImage(bitmap, 0, 0, largura, altura);
    const tipo = arquivo.type === PNG ? PNG : 'image/jpeg';
    const reduzida = await new Promise((pronto) => { canvas.toBlob(pronto, tipo, QUALIDADE); });
    if (!reduzida) return arquivo;
    const nome = tipo === PNG ? arquivo.name : nomeEmJpeg(arquivo.name);
    return new File([reduzida], nome, { type: tipo, lastModified: arquivo.lastModified });
}

function ambienteDoNavegador() {
    if (!globalThis.createImageBitmap || !globalThis.DataTransfer) return null;
    return {
        criarBitmap: (arquivo) => globalThis.createImageBitmap(arquivo, { imageOrientation: 'from-image' }),
        criarCanvas: (largura, altura) => Object.assign(document.createElement('canvas'), { width: largura, height: altura }),
        novaLista: () => new globalThis.DataTransfer(),
    };
}

/* Troca as fotos escolhidas pelas reduzidas. Enquanto isso, o botão de salvar fica desligado. */
async function reduzirFotosDoCampo(campo, ambiente = ambienteDoNavegador()) {
    if (!ambiente || campo.files.length === 0) return;
    const salvar = campo.form?.querySelector('[type="submit"]');
    if (salvar) salvar.disabled = true;
    try {
        const fotos = await Promise.all([...campo.files].map((arquivo) => reduzirFoto(arquivo, ambiente).catch(() => arquivo)));
        const lista = ambiente.novaLista();
        fotos.forEach((foto) => lista.items.add(foto));
        campo.files = lista.files;
    } finally {
        if (salvar) salvar.disabled = false;
    }
}

function iniciarReducaoDeFotos(raiz = document) {
    raiz.querySelectorAll('input[type="file"][data-reduzir-fotos]').forEach((campo) => {
        campo.addEventListener('change', () => reduzirFotosDoCampo(campo));
    });
}

document.addEventListener('DOMContentLoaded', () => iniciarReducaoDeFotos());

/* istanbul ignore else */
// Stryker disable next-line all: no Jest `module` sempre existe; a linha só serve para os testes importarem o arquivo.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { medidasReduzidas, nomeEmJpeg, reduzirFoto, reduzirFotosDoCampo, ambienteDoNavegador, iniciarReducaoDeFotos };
}

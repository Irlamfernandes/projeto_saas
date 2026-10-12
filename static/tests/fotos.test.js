/**
 * @jest-environment jsdom
 */
const fotos = require('../js/fotos');

function arquivo(nome, tipo = 'image/jpeg') {
    return new File(['conteúdo'], nome, { type: tipo, lastModified: 123 });
}

function ambienteFalso({ largura = 4000, altura = 3000, blob = true, falhar = [] } = {}) {
    const desenhos = [];
    const pedidos = [];
    const lista = [];
    return {
        desenhos,
        pedidos,
        criarBitmap: jest.fn(async (foto) => {
            if (falhar.includes(foto.name)) throw new Error('não deu para ler');
            return { width: largura, height: altura };
        }),
        criarCanvas: jest.fn((l, a) => ({
            getContext: () => ({ drawImage: (...args) => desenhos.push({ args, l, a }) }),
            toBlob: (pronto, tipo, qualidade) => {
                pedidos.push({ tipo, qualidade });
                pronto(blob ? new Blob(['menor'], { type: tipo }) : null);
            },
        })),
        novaLista: () => ({ items: { add: (foto) => lista.push(foto) }, files: lista }),
    };
}

function campoComFotos(lista, comFormulario = true) {
    document.body.innerHTML = comFormulario
        ? '<form><input type="file" data-reduzir-fotos><button type="submit">Salvar</button></form>'
        : '<input type="file" data-reduzir-fotos>';
    const campo = document.querySelector('input');
    let atuais = lista;
    Object.defineProperty(campo, 'files', { get: () => atuais, set: (novas) => { atuais = novas; } });
    return campo;
}

describe('medidas e nomes', () => {
    test('reduz o maior lado para 1600 px mantendo a proporção', () => {
        expect(fotos.medidasReduzidas(4000, 3000)).toEqual({ largura: 1600, altura: 1200 });
        expect(fotos.medidasReduzidas(3000, 4000)).toEqual({ largura: 1200, altura: 1600 });
        expect(fotos.medidasReduzidas(3333, 1000)).toEqual({ largura: 1600, altura: 480 });
        expect(fotos.medidasReduzidas(1000, 500)).toEqual({ largura: 1000, altura: 500 });
        expect(fotos.medidasReduzidas(100, 50, 10)).toEqual({ largura: 10, altura: 5 });
    });

    test('nome do arquivo em JPEG', () => {
        expect(fotos.nomeEmJpeg('IMG_0001.HEIC')).toBe('IMG_0001.jpg');
        expect(fotos.nomeEmJpeg('a.b.png')).toBe('a.b.jpg');
        expect(fotos.nomeEmJpeg('foto')).toBe('foto.jpg');
        expect(fotos.nomeEmJpeg('.oculta')).toBe('.oculta.jpg');
    });
});

describe('reduzirFoto', () => {
    test('foto grande vira JPEG de 1600 px', async () => {
        const ambiente = ambienteFalso();
        const original = arquivo('IMG.HEIC', 'image/heic');

        const reduzida = await fotos.reduzirFoto(original, ambiente);

        expect(ambiente.criarCanvas).toHaveBeenCalledWith(1600, 1200);
        expect(ambiente.desenhos[0].args).toEqual([{ width: 4000, height: 3000 }, 0, 0, 1600, 1200]);
        expect(ambiente.pedidos).toEqual([{ tipo: 'image/jpeg', qualidade: 0.85 }]);
        expect(reduzida.name).toBe('IMG.jpg');
        expect(reduzida.type).toBe('image/jpeg');
        expect(reduzida.lastModified).toBe(123);
        expect(reduzida.size).toBe(5); // 'menor': o conteúdo veio do canvas
    });

    test('PNG continua PNG, com o mesmo nome (pode ter fundo transparente)', async () => {
        const ambiente = ambienteFalso();
        const reduzida = await fotos.reduzirFoto(arquivo('logo.png', 'image/png'), ambiente);
        expect(ambiente.pedidos[0].tipo).toBe('image/png');
        expect(reduzida.name).toBe('logo.png');
        expect(reduzida.type).toBe('image/png');
    });

    test('foto de até 1600 px segue como veio', async () => {
        const original = arquivo('pequena.jpg');
        for (const [largura, altura] of [[1600, 900], [900, 1600], [800, 600]]) {
            const ambiente = ambienteFalso({ largura, altura });
            expect(await fotos.reduzirFoto(original, ambiente)).toBe(original);
            expect(ambiente.criarCanvas).not.toHaveBeenCalled();
        }
    });

    test('se o navegador não gerar a imagem reduzida, segue a original', async () => {
        const original = arquivo('foto.jpg');
        expect(await fotos.reduzirFoto(original, ambienteFalso({ blob: false }))).toBe(original);
    });
});

describe('reduzirFotosDoCampo', () => {
    test('troca as fotos escolhidas pelas reduzidas, com o botão desligado enquanto isso', async () => {
        const campo = campoComFotos([arquivo('a.jpg'), arquivo('b.heic', 'image/heic')]);
        const botao = document.querySelector('button');
        const ambiente = ambienteFalso({ falhar: ['b.heic'] });

        const andamento = fotos.reduzirFotosDoCampo(campo, ambiente);
        expect(botao.disabled).toBe(true);
        await andamento;

        expect(botao.disabled).toBe(false);
        expect(campo.files.map((foto) => foto.name)).toEqual(['a.jpg', 'b.heic']); // a que não deu para ler segue
        expect(campo.files[0].type).toBe('image/jpeg');
        expect(campo.files[0].size).toBe(5);
    });

    test('sem formulário ou sem foto escolhida, não quebra', async () => {
        const solto = campoComFotos([arquivo('a.jpg')], false);
        await fotos.reduzirFotosDoCampo(solto, ambienteFalso());
        expect(solto.files[0].size).toBe(5);

        const vazio = campoComFotos([]);
        const ambiente = ambienteFalso();
        await fotos.reduzirFotosDoCampo(vazio, ambiente);
        expect(ambiente.criarBitmap).not.toHaveBeenCalled();
        expect(document.querySelector('button').disabled).toBe(false);
    });

    test('navegador sem os recursos necessários: as fotos seguem como vieram', async () => {
        const original = [arquivo('a.jpg')];
        const campo = campoComFotos(original);
        await fotos.reduzirFotosDoCampo(campo, null);
        expect(campo.files).toBe(original);
    });

    test('se algo der errado no meio, o botão volta a funcionar', async () => {
        const campo = campoComFotos([arquivo('a.jpg')]);
        const ambiente = { ...ambienteFalso(), novaLista: () => { throw new Error('sem DataTransfer'); } };
        await expect(fotos.reduzirFotosDoCampo(campo, ambiente)).rejects.toThrow('sem DataTransfer');
        expect(document.querySelector('button').disabled).toBe(false);
    });
});

describe('navegador', () => {
    afterEach(() => {
        delete globalThis.createImageBitmap;
        delete globalThis.DataTransfer;
    });

    test('sem createImageBitmap ou sem DataTransfer, não reduz', () => {
        expect(fotos.ambienteDoNavegador()).toBeNull();
        globalThis.createImageBitmap = jest.fn();
        expect(fotos.ambienteDoNavegador()).toBeNull();
        delete globalThis.createImageBitmap;
        globalThis.DataTransfer = jest.fn();
        expect(fotos.ambienteDoNavegador()).toBeNull();
    });

    test('usa os recursos do navegador, respeitando a rotação da foto', () => {
        globalThis.createImageBitmap = jest.fn(() => 'bitmap');
        globalThis.DataTransfer = jest.fn(function () { this.items = 'itens'; });
        const ambiente = fotos.ambienteDoNavegador();
        const foto = arquivo('a.jpg');

        expect(ambiente.criarBitmap(foto)).toBe('bitmap');
        expect(globalThis.createImageBitmap).toHaveBeenCalledWith(foto, { imageOrientation: 'from-image' });
        const canvas = ambiente.criarCanvas(30, 20);
        expect([canvas.tagName, canvas.width, canvas.height]).toEqual(['CANVAS', 30, 20]);
        expect(ambiente.novaLista().items).toBe('itens');
    });

    test('liga sozinho nos campos marcados quando a página carrega', async () => {
        globalThis.createImageBitmap = jest.fn(async () => ({ width: 10, height: 10 }));
        globalThis.DataTransfer = jest.fn(function () {
            const lista = [];
            this.items = { add: (foto) => lista.push(foto) };
            this.files = lista;
        });
        const campo = campoComFotos([arquivo('a.jpg')]);
        document.body.insertAdjacentHTML('beforeend', '<input type="file" id="outro">');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        campo.dispatchEvent(new Event('change'));
        await new Promise((pronto) => { setTimeout(pronto, 0); });

        expect(globalThis.createImageBitmap).toHaveBeenCalledTimes(1);
        expect(campo.files.map((foto) => foto.name)).toEqual(['a.jpg']);
    });
});

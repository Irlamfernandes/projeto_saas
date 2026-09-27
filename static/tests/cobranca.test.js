/**
 * @jest-environment jsdom
 */
const { copiarPix, acompanharCobranca } = require('../js/cobranca.js');

function montar() {
    document.body.innerHTML = `
        <textarea id="pix">000201PIX</textarea>
        <button data-copiar="pix"><span>Copiar código</span></button>
        <div data-acompanhar-cobranca data-url-situacao="/situacao/"></div>`;
    return { botao: document.querySelector('button'), campo: document.getElementById('pix'), area: document.querySelector('[data-acompanhar-cobranca]') };
}

const respostaJson = (dados, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(dados) });
const esperarVolta = async () => { jest.advanceTimersByTime(5000); for (let i = 0; i < 5; i += 1) await Promise.resolve(); };

describe('copiar o Pix', () => {
    test('copia o código e avisa', async () => {
        const { botao } = montar();
        const writeText = jest.fn(() => Promise.resolve());
        Object.assign(navigator, { clipboard: { writeText } });

        await copiarPix(botao);

        expect(writeText).toHaveBeenCalledWith('000201PIX');
        expect(botao.textContent).toBe('Código copiado!');
    });

    test('botão sem texto separado: o aviso vai no próprio botão', async () => {
        document.body.innerHTML = '<textarea id="pix">000201PIX</textarea><button data-copiar="pix">Copiar</button>';
        Object.assign(navigator, { clipboard: { writeText: jest.fn(() => Promise.resolve()) } });
        const botao = document.querySelector('button');

        await copiarPix(botao);

        expect(botao.textContent).toBe('Código copiado!');
    });

    test('sem permissão para copiar, seleciona o texto', async () => {
        const { botao, campo } = montar();
        Object.assign(navigator, { clipboard: { writeText: () => Promise.reject(new Error('negado')) } });

        await copiarPix(botao);

        expect(document.activeElement).toBe(campo);
        expect(campo.selectionEnd).toBe(campo.value.length);
        expect(botao.textContent).toContain('Selecionado');
    });
});

describe('acompanhar a cobrança', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => { jest.useRealTimers(); delete global.fetch; });

    test('enquanto está pendente continua perguntando, sem recarregar', async () => {
        const { area } = montar();
        global.fetch = jest.fn(() => respostaJson({ status: 'pendente' }));
        const recarregar = jest.fn();
        const parar = acompanharCobranca(area, { recarregar });

        await esperarVolta();
        await esperarVolta();

        expect(global.fetch).toHaveBeenCalledTimes(2);
        expect(global.fetch).toHaveBeenCalledWith('/situacao/', expect.objectContaining({ cache: 'no-store' }));
        expect(recarregar).not.toHaveBeenCalled();
        parar();
    });

    test('quando é confirmada (ou expira) recarrega a tela uma vez e para', async () => {
        const { area } = montar();
        global.fetch = jest.fn(() => respostaJson({ status: 'paga' }));
        const recarregar = jest.fn();
        acompanharCobranca(area, { recarregar });

        await esperarVolta();
        await esperarVolta();

        expect(recarregar).toHaveBeenCalledTimes(1);
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    test('erro de rede ou resposta ruim não quebra: tenta de novo', async () => {
        const { area } = montar();
        global.fetch = jest.fn()
            .mockImplementationOnce(() => Promise.reject(new Error('offline')))
            .mockImplementationOnce(() => respostaJson({}, false))
            .mockImplementation(() => respostaJson({ status: 'paga' }));
        const recarregar = jest.fn();
        acompanharCobranca(area, { recarregar });

        await esperarVolta();
        await esperarVolta();
        await esperarVolta();

        expect(recarregar).toHaveBeenCalledTimes(1);
    });

    test('conferência ainda em andamento: não pergunta de novo por cima', async () => {
        const { area } = montar();
        global.fetch = jest.fn(() => new Promise(() => {})); // servidor demorando
        const parar = acompanharCobranca(area, { recarregar: jest.fn() });

        await esperarVolta();
        await esperarVolta();

        expect(global.fetch).toHaveBeenCalledTimes(1);
        parar();
    });

    test('sem recarregar informado, recarrega a própria página', async () => {
        const { area } = montar();
        global.fetch = jest.fn(() => respostaJson({ status: 'paga' }));
        const erroDoJsdom = jest.spyOn(console, 'error').mockImplementation(() => {}); // o jsdom não navega de verdade

        acompanharCobranca(area);
        await esperarVolta();

        expect(erroDoJsdom.mock.calls.some(([erro]) => String(erro?.message ?? erro).includes('navigation'))).toBe(true);
        erroDoJsdom.mockRestore();
    });

    test('liga sozinho ao carregar a página', async () => {
        montar();
        global.fetch = jest.fn(() => respostaJson({ status: 'pendente' }));
        document.dispatchEvent(new Event('DOMContentLoaded'));
        await esperarVolta();
        expect(global.fetch).toHaveBeenCalled();
    });
});

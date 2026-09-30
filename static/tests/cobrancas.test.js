/**
 * @jest-environment jsdom
 */
const { anotarLembrete, aLembrar, iniciarCobrancas } = require('../js/cobrancas.js');

function linha({ nome, link = `https://wa.me/55${nome}`, lembrado = false }) {
    return `<li data-cobranca data-nome="${nome}" data-link="${link}" data-mensagem="Olá, ${nome}!"
                data-lembrete="/clientes/${nome}/lembrete/" ${lembrado ? 'data-lembrado' : ''}>
                <span class="hidden" data-selo-lembrado></span>
                <a href="${link}" data-enviar-lembrete></a>
            </li>`;
}

function montar(linhas, { comJanela = true } = {}) {
    document.body.innerHTML = `
        <section data-cobrancas>
            <input type="hidden" name="csrfmiddlewaretoken" value="tok">
            <button data-cobrar-todos></button>
            <ul>${linhas.join('')}</ul>
        </section>
        ${comJanela ? `<dialog id="cobrar-todos">
            <div data-etapa><span data-passo></span><p data-cliente></p><p data-texto></p>
                <button data-pular></button><a data-enviar></a></div>
            <div class="hidden" data-fim></div>
        </dialog>` : ''}`;
    const janela = document.getElementById('cobrar-todos');
    if (janela) janela.showModal = jest.fn();
    const enviar = jest.fn(() => Promise.resolve());
    iniciarCobrancas(document, enviar);
    const $ = (seletor) => document.querySelector(seletor);
    return { enviar, janela, $ };
}

beforeAll(() => {
    // O jsdom não navega: o clique no link só dispara o que o sistema faz.
    HTMLAnchorElement.prototype.click = function () { this.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); };
});

describe('anotar lembrete', () => {
    test('marca na tela e avisa o servidor com o token', async () => {
        const { enviar, $ } = montar([linha({ nome: 'Ana' })]);
        const li = $('[data-cobranca]');

        await anotarLembrete(li, enviar);

        expect(li.dataset.lembrado).toBe('');
        expect(li.querySelector('[data-selo-lembrado]').classList.contains('hidden')).toBe(false);
        expect(enviar).toHaveBeenCalledWith('/clientes/Ana/lembrete/', {
            method: 'POST', headers: { 'X-CSRFToken': 'tok' }, credentials: 'same-origin',
        });
    });

    test('falha na internet não quebra a tela', async () => {
        const { $ } = montar([linha({ nome: 'Ana' })]);
        await expect(anotarLembrete($('[data-cobranca]'), () => Promise.reject(new Error('offline')))).resolves.toBeUndefined();
    });

    test('sem o token ainda tenta anotar', async () => {
        document.body.innerHTML = linha({ nome: 'Ana' });
        const enviar = jest.fn(() => Promise.resolve());
        await anotarLembrete(document.querySelector('[data-cobranca]'), enviar);
        expect(enviar.mock.calls[0][1].headers).toEqual({ 'X-CSRFToken': undefined });
    });

    test('o botão Cobrar de cada cliente anota o lembrete', () => {
        const { enviar, $ } = montar([linha({ nome: 'Ana' })]);
        $('[data-enviar-lembrete]').click();
        expect(enviar).toHaveBeenCalledTimes(1);
    });
});

describe('quem falta lembrar', () => {
    test('fora quem já foi lembrado hoje e quem não tem telefone', () => {
        const { $ } = montar([linha({ nome: 'Ana' }), linha({ nome: 'Bia', lembrado: true }), linha({ nome: 'Caio', link: '' })]);
        expect(aLembrar($('[data-cobrancas]')).map((li) => li.dataset.nome)).toEqual(['Ana']);
    });
});

describe('cobrar todos', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => jest.useRealTimers());

    test('passa um cliente por vez, anotando cada envio', () => {
        const { enviar, janela, $ } = montar([linha({ nome: 'Ana' }), linha({ nome: 'Bia', lembrado: true }), linha({ nome: 'Caio' })]);

        $('[data-cobrar-todos]').click();
        expect(janela.showModal).toHaveBeenCalled();
        expect($('[data-passo]').textContent).toBe('1 de 2');
        expect($('[data-cliente]').textContent).toBe('Ana');
        expect($('[data-texto]').textContent).toBe('Olá, Ana!');
        expect($('[data-enviar]').getAttribute('href')).toBe('https://wa.me/55Ana');

        $('[data-enviar]').click();
        expect($('[data-enviar]').getAttribute('href')).toBe('https://wa.me/55Ana'); // o link aberto é o deste cliente
        jest.runAllTimers();
        expect(enviar).toHaveBeenCalledWith('/clientes/Ana/lembrete/', expect.anything());
        expect($('[data-passo]').textContent).toBe('2 de 2');
        expect($('[data-cliente]').textContent).toBe('Caio');

        $('[data-pular]').click();
        expect($('[data-etapa]').classList.contains('hidden')).toBe(true);
        expect($('[data-fim]').classList.contains('hidden')).toBe(false);
        expect(enviar).toHaveBeenCalledTimes(1);
    });

    test('abrir de novo recomeça só com quem falta', () => {
        const { $ } = montar([linha({ nome: 'Ana' }), linha({ nome: 'Caio' })]);
        $('[data-cobrar-todos]').click();
        $('[data-enviar]').click();
        jest.runAllTimers();

        $('[data-cobrar-todos]').click();

        expect($('[data-passo]').textContent).toBe('1 de 1');
        expect($('[data-cliente]').textContent).toBe('Caio');
    });

    test('ninguém para lembrar vai direto para o fim', () => {
        const { $ } = montar([linha({ nome: 'Ana', lembrado: true })]);
        $('[data-cobrar-todos]').click();
        expect($('[data-fim]').classList.contains('hidden')).toBe(false);
    });
});

describe('página sem cobranças', () => {
    test('sem o quadro ou sem a janela não quebra', () => {
        document.body.innerHTML = '';
        expect(() => iniciarCobrancas(document, jest.fn())).not.toThrow();
        expect(() => montar([linha({ nome: 'Ana' })], { comJanela: false })).not.toThrow();
    });

    test('ao carregar a página liga os botões usando o fetch do navegador', () => {
        globalThis.fetch = jest.fn(() => Promise.resolve());
        document.body.innerHTML = `<section data-cobrancas>${linha({ nome: 'Ana' })}</section>`;
        document.dispatchEvent(new Event('DOMContentLoaded'));
        document.querySelector('[data-enviar-lembrete]').click();
        expect(globalThis.fetch).toHaveBeenCalledWith('/clientes/Ana/lembrete/', expect.anything());
        delete globalThis.fetch;
    });
});

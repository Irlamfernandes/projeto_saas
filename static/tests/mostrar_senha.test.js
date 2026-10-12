/**
 * @jest-environment jsdom
 */
const { iniciarOlhosDaSenha } = require('../js/mostrar_senha');

function montar() {
    document.body.innerHTML = `
        <form id="f"><input type="password" id="senha" class="entrada"><input type="text" id="nome"></form>
        <input type="password" id="solta">`;
    iniciarOlhosDaSenha();
    return {
        campo: document.getElementById('senha'),
        botao: document.querySelector('#f .olho-da-senha'),
    };
}

describe('olhinho da senha', () => {
    test('coloca um botão ao lado de cada campo de senha, e só neles', () => {
        const { campo, botao } = montar();
        expect(document.querySelectorAll('.olho-da-senha')).toHaveLength(2);
        expect(campo.parentElement.className).toBe('campo-senha');
        expect(campo.nextElementSibling).toBe(botao);
        expect(document.getElementById('nome').parentElement.id).toBe('f');
        expect(botao.type).toBe('button'); // não envia o formulário
        expect(botao.getAttribute('aria-label')).toBe('Mostrar senha');
        expect(botao.title).toBe('Mostrar ou esconder a senha');
        expect(botao.getAttribute('aria-pressed')).toBe('false');
    });

    test('o desenho é um olho com o risco que aparece com a senha à mostra', () => {
        const { botao } = montar();
        const svg = botao.querySelector('svg');
        expect(svg.namespaceURI).toBe('http://www.w3.org/2000/svg');
        expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
        expect(svg.getAttribute('aria-hidden')).toBe('true');
        expect(svg.getAttribute('class')).toBe('olho-da-senha-icone');
        expect([...svg.querySelectorAll('path')].map((p) => p.getAttribute('d'))).toEqual([
            'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z', 'M3 3l18 18',
        ]);
    });

    test('clicar mostra, clicar de novo esconde, e o cursor volta para o campo', () => {
        const { campo, botao } = montar();
        botao.click();
        expect(campo.type).toBe('text');
        expect(botao.getAttribute('aria-pressed')).toBe('true');
        expect(document.activeElement).toBe(campo);
        botao.click();
        expect(campo.type).toBe('password');
        expect(botao.getAttribute('aria-pressed')).toBe('false');
    });

    test('ao enviar, a senha volta a ficar escondida', () => {
        const { campo, botao } = montar();
        botao.click();
        document.getElementById('f').dispatchEvent(new Event('submit'));
        expect(campo.type).toBe('password');
        expect(botao.getAttribute('aria-pressed')).toBe('false');
    });

    test('campo fora de formulário também ganha o olhinho', () => {
        montar();
        const solta = document.getElementById('solta');
        solta.nextElementSibling.click();
        expect(solta.type).toBe('text');
    });

    test('chamar de novo não coloca um segundo olhinho', () => {
        montar();
        iniciarOlhosDaSenha();
        expect(document.querySelectorAll('.olho-da-senha')).toHaveLength(2);
    });

    test('liga sozinho quando a página termina de carregar', () => {
        document.body.innerHTML = '<input type="password">';
        document.dispatchEvent(new Event('DOMContentLoaded'));
        expect(document.querySelectorAll('.olho-da-senha')).toHaveLength(1);
    });
});

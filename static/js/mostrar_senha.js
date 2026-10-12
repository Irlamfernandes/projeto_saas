/* Olhinho ao lado de todo campo de senha (site e admin): mostra ou esconde o que foi digitado.
   Antes de enviar, a senha volta a ficar escondida, para o navegador não guardá-la como texto comum. */
const SVG = 'http://www.w3.org/2000/svg';
const DESENHO_DO_OLHO = ['M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z'];
const RISCO = 'M3 3l18 18'; // aparece quando a senha está à mostra: clicar de novo esconde

function desenharOlho() {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', 'olho-da-senha-icone');
    [...DESENHO_DO_OLHO, RISCO].forEach((caminho) => {
        const traco = document.createElementNS(SVG, 'path');
        traco.setAttribute('d', caminho);
        svg.append(traco);
    });
    return svg;
}

function mostrarSenha(campo, botao, visivel) {
    campo.type = visivel ? 'text' : 'password';
    botao.setAttribute('aria-pressed', String(visivel));
}

function adicionarOlho(campo) {
    if (campo.parentElement.classList.contains('campo-senha')) return;
    const caixa = document.createElement('span');
    caixa.className = 'campo-senha';
    campo.before(caixa);
    caixa.append(campo);

    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'olho-da-senha';
    botao.setAttribute('aria-label', 'Mostrar senha');
    botao.title = 'Mostrar ou esconder a senha';
    botao.append(desenharOlho());
    mostrarSenha(campo, botao, false);
    botao.addEventListener('click', () => {
        mostrarSenha(campo, botao, campo.type === 'password');
        campo.focus();
    });
    campo.form?.addEventListener('submit', () => mostrarSenha(campo, botao, false));
    caixa.append(botao);
}

function iniciarOlhosDaSenha(raiz = document) {
    raiz.querySelectorAll('input[type="password"]').forEach(adicionarOlho);
}

document.addEventListener('DOMContentLoaded', () => iniciarOlhosDaSenha());

/* istanbul ignore else */
// Stryker disable next-line all: no Jest `module` sempre existe; a linha só serve para os testes importarem o arquivo.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { iniciarOlhosDaSenha };
}

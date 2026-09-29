/* Cobranças do Início. "Cobrar" abre o WhatsApp com a mensagem pronta e anota "lembrado hoje" no sistema.
   "Cobrar todos" passa cliente por cliente: cada envio é um toque do dono (nada é mandado sozinho). */

function anotarLembrete(linha, enviar) {
    const token = document.querySelector('[data-cobrancas] [name="csrfmiddlewaretoken"]')?.value;
    linha.dataset.lembrado = '';
    linha.querySelector('[data-selo-lembrado]').classList.remove('hidden');
    // Se a anotação falhar (internet caiu), a mensagem já foi aberta: o dono não perde nada.
    return enviar(linha.dataset.lembrete, { method: 'POST', headers: { 'X-CSRFToken': token }, credentials: 'same-origin' })
        .catch(() => {});
}

/* Quem ainda falta lembrar hoje e tem telefone para o WhatsApp. */
function aLembrar(quadro) {
    return [...quadro.querySelectorAll('[data-cobranca]')].filter((linha) => linha.dataset.link && !('lembrado' in linha.dataset));
}

function iniciarCobrarTodos(quadro, janela, enviar) {
    const botao = quadro.querySelector('[data-cobrar-todos]');
    if (!botao || !janela) return;
    const etapa = janela.querySelector('[data-etapa]');
    const fim = janela.querySelector('[data-fim]');
    const enviarNoWhatsApp = janela.querySelector('[data-enviar]');
    let fila; // preenchida ao abrir a janela
    let posicao = 0;

    function mostrar() {
        const linha = fila[posicao];
        // Classe, e não o atributo hidden: o display: grid do layout venceria o atributo.
        etapa.classList.toggle('hidden', !linha);
        fim.classList.toggle('hidden', Boolean(linha));
        if (!linha) return;
        janela.querySelector('[data-passo]').textContent = `${posicao + 1} de ${fila.length}`;
        janela.querySelector('[data-cliente]').textContent = linha.dataset.nome;
        janela.querySelector('[data-texto]').textContent = linha.dataset.mensagem;
        enviarNoWhatsApp.href = linha.dataset.link;
    }

    function proximo() {
        posicao += 1;
        mostrar();
    }

    botao.addEventListener('click', () => {
        fila = aLembrar(quadro);
        posicao = 0;
        mostrar();
        janela.showModal();
    });
    enviarNoWhatsApp.addEventListener('click', () => {
        anotarLembrete(fila[posicao], enviar);
        // O link só troca depois que o navegador abriu o WhatsApp deste cliente.
        setTimeout(proximo, 0);
    });
    janela.querySelector('[data-pular]').addEventListener('click', proximo);
}

function iniciarCobrancas(raiz = document, enviar = (...args) => globalThis.fetch(...args)) {
    const quadro = raiz.querySelector('[data-cobrancas]');
    if (!quadro) return;
    quadro.querySelectorAll('[data-enviar-lembrete]').forEach((link) => {
        link.addEventListener('click', () => anotarLembrete(link.closest('[data-cobranca]'), enviar));
    });
    iniciarCobrarTodos(quadro, raiz.querySelector('#cobrar-todos'), enviar);
}

document.addEventListener('DOMContentLoaded', () => iniciarCobrancas());

/* istanbul ignore else */
// Stryker disable next-line all: no Jest `module` sempre existe; a linha só serve para os testes importarem o arquivo.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { anotarLembrete, aLembrar, iniciarCobrancas };
}

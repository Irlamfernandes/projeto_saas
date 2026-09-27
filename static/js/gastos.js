/* Compra com vários produtos (interfaces/gastos.html): "Outro produto" copia a linha do <template>,
   escolher o produto sugere o custo atual e a unidade dele, e o total é somado em centavos, como no servidor. */

const reaisDaCompra = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

/* Quantidade × custo em centavos, com contas inteiras (0,35 kg × R$ 39,90 = R$ 13,97). */
function subtotalDaCompra(quantidade, custo) {
    const centavos = Math.round(custo * 100) * Math.round(quantidade * 1000);
    return Math.round(centavos / 1000) / 100;
}

function totalDaCompra(formulario) {
    return [...formulario.querySelectorAll('[data-item-compra]')].reduce((soma, linha) => {
        const quantidade = Number(linha.querySelector('[name="item_quantidade"]').value) || 0;
        const custo = Number(linha.querySelector('[name="item_custo"]').value) || 0;
        return soma + subtotalDaCompra(quantidade, custo);
    }, 0);
}

function prepararLinha(linha, atualizarTotal) {
    const produto = linha.querySelector('[data-produto-compra]');
    const quantidade = linha.querySelector('[name="item_quantidade"]');
    const custo = linha.querySelector('[name="item_custo"]');
    produto.addEventListener('change', () => {
        const opcao = produto.selectedOptions[0];
        linha.querySelector('[data-sigla-compra]').textContent = opcao.dataset.sigla || 'un.';
        // O mínimo acompanha o passo: com passo 1 e mínimo 0,001 o navegador só aceitaria 1,001, 2,001...
        quantidade.step = opcao.dataset.casas > 0 ? String(10 ** -Number(opcao.dataset.casas)) : '1';
        quantidade.min = quantidade.step;
        // Só sugere o custo se ainda não foi digitado: não apaga o que a pessoa escreveu.
        if (!custo.value && Number(opcao.dataset.custo) > 0) custo.value = opcao.dataset.custo;
        atualizarTotal();
    });
    quantidade.addEventListener('input', atualizarTotal);
    custo.addEventListener('input', atualizarTotal);
}

function iniciarCompra(formulario) {
    const lista = formulario.querySelector('[data-itens-compra]');
    const modelo = formulario.querySelector('[data-modelo-item-compra]');
    const total = formulario.querySelector('[data-total-compra]');
    const atualizarTotal = () => { total.textContent = reaisDaCompra.format(totalDaCompra(formulario)); };

    lista.querySelectorAll('[data-item-compra]').forEach((linha) => prepararLinha(linha, atualizarTotal));
    formulario.querySelector('[data-adicionar-item-compra]').addEventListener('click', () => {
        const linha = modelo.content.firstElementChild.cloneNode(true);
        prepararLinha(linha, atualizarTotal);
        lista.append(linha);
        linha.querySelector('[data-produto-compra]').focus();
    });
    lista.addEventListener('click', (evento) => {
        const botao = evento.target.closest('[data-remover-item-compra]');
        if (!botao) return;
        const linha = botao.closest('[data-item-compra]');
        // A primeira linha fica (só é limpa): a compra sempre tem onde escolher um produto.
        if (lista.children.length > 1) {
            linha.remove();
        } else {
            linha.querySelectorAll('select, input').forEach((campo) => { campo.value = ''; });
        }
        atualizarTotal();
    });
    atualizarTotal();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form[data-compra]').forEach(iniciarCompra);
});

/* istanbul ignore else */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { subtotalDaCompra, totalDaCompra, iniciarCompra };
}

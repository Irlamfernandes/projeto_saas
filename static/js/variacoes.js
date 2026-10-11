/* Variações no cadastro do produto (interfaces/_variacoes_do_produto.html). "Adicionar variação" copia a linha do
   <template> (até o máximo) e a lixeira tira a linha. Com alguma variação com nome, a quantidade do produto fica só
   para leitura e mostra a soma delas: quem guarda o estoque são as variações. Sem controle de estoque, as
   quantidades das variações somem. */
const NOME = '[name="variacao_nome"]';
const QUANTIDADE = '[name="variacao_quantidade"]';

/* Soma em milésimos inteiros (0,1 + 0,2 dá 0,3 e não 0,30000000000000004). Vazio ou inválido conta como zero. */
function somarQuantidades(textos) {
    const milesimos = textos.reduce((soma, texto) => soma + (Math.round(Number(texto.replace(',', '.')) * 1000) || 0), 0);
    return String(milesimos / 1000);
}

function iniciarVariacoes(bloco) {
    const formulario = bloco.closest('form');
    const lista = bloco.querySelector('[data-lista-variacoes]');
    const modelo = bloco.querySelector('[data-modelo-variacao]');
    const adicionar = bloco.querySelector('[data-adicionar-variacao]');
    const unidade = formulario.querySelector('[name="unidade"]');
    const semControle = formulario.querySelector('[name="sem_controle_de_estoque"]');
    const estoque = formulario.querySelector('[name="quantidade_estoque"]');

    function atualizar() {
        const linhas = [...lista.children];
        const comNome = linhas.filter((linha) => linha.querySelector(NOME).value.trim());
        const passo = String(10 ** -Number(unidade.selectedOptions[0].dataset.casas));
        linhas.forEach((linha) => {
            linha.querySelector(QUANTIDADE).step = passo;
            linha.querySelector('[data-quantidade-da-variacao]').classList.toggle('hidden', semControle.checked);
        });
        estoque.readOnly = comNome.length > 0;
        if (estoque.readOnly) estoque.value = somarQuantidades(comNome.map((linha) => linha.querySelector(QUANTIDADE).value));
        adicionar.disabled = linhas.length >= Number(bloco.dataset.maximo);
    }

    adicionar.addEventListener('click', () => {
        lista.append(modelo.content.firstElementChild.cloneNode(true));
        lista.lastElementChild.querySelector(NOME).focus();
        atualizar();
    });
    lista.addEventListener('click', (evento) => {
        const botao = evento.target.closest('[data-remover-variacao]');
        if (!botao) return;
        botao.closest('[data-variacao-produto]').remove();
        atualizar();
    });
    formulario.addEventListener('input', atualizar);
    formulario.addEventListener('change', atualizar);
    atualizar();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-variacoes-produto]').forEach(iniciarVariacoes);
});

/* istanbul ignore else */
// Stryker disable next-line all: no Jest `module` sempre existe; a linha só serve para os testes importarem o arquivo.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { somarQuantidades, iniciarVariacoes };
}

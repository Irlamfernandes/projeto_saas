/**
 * @jest-environment jsdom
 */
const { somarQuantidades, iniciarVariacoes } = require('../js/variacoes');

const LINHA = `<fieldset data-variacao-produto><input name="variacao_id"><input name="variacao_nome">
    <label data-quantidade-da-variacao><input name="variacao_quantidade" type="number"></label>
    <input name="variacao_acrescimo"><button type="button" data-remover-variacao><svg></svg></button></fieldset>`;

function montar({ linhas = 0, maximo = 3, semControle = false } = {}) {
    document.body.innerHTML = `<form>
        <select name="unidade"><option value="un" data-casas="0">un</option><option value="kg" data-casas="3">kg</option></select>
        <input type="number" name="quantidade_estoque" value="7">
        <input type="checkbox" name="sem_controle_de_estoque"${semControle ? ' checked' : ''}>
        <details data-variacoes-produto data-maximo="${maximo}">
            <div data-lista-variacoes>${LINHA.repeat(linhas)}</div>
            <button type="button" data-adicionar-variacao>Adicionar</button>
            <template data-modelo-variacao>${LINHA}</template>
        </details></form>`;
    iniciarVariacoes(document.querySelector('[data-variacoes-produto]'));
    return {
        estoque: document.querySelector('[name="quantidade_estoque"]'),
        adicionar: document.querySelector('[data-adicionar-variacao]'),
        linhas: () => [...document.querySelectorAll('[data-lista-variacoes] [data-variacao-produto]')],
    };
}

function preencher(linha, nome, quantidade) {
    linha.querySelector('[name="variacao_nome"]').value = nome;
    const campo = linha.querySelector('[name="variacao_quantidade"]');
    campo.value = quantidade;
    campo.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('somarQuantidades', () => {
    test('soma em milésimos, com vírgula ou ponto; vazio e texto contam zero', () => {
        expect(somarQuantidades(['0.1', '0,2'])).toBe('0.3');
        expect(somarQuantidades(['10', '', 'abc', '5'])).toBe('15');
        expect(somarQuantidades([])).toBe('0');
    });
});

describe('variações no cadastro do produto', () => {
    test('"Adicionar variação" copia a linha do modelo, foca o nome e para no máximo', () => {
        const { adicionar, linhas } = montar({ maximo: 2 });
        expect(adicionar.disabled).toBe(false);
        adicionar.click();
        expect(linhas()).toHaveLength(1);
        expect(document.activeElement).toBe(linhas()[0].querySelector('[name="variacao_nome"]'));
        adicionar.click();
        expect(linhas()).toHaveLength(2);
        expect(adicionar.disabled).toBe(true);
    });

    test('com variações, o estoque do produto vira a soma delas e fica só para leitura', () => {
        const { estoque, linhas } = montar({ linhas: 3 });
        expect([estoque.readOnly, estoque.value]).toEqual([false, '7']); // sem nome ainda: vale o digitado

        preencher(linhas()[0], 'Azul P', '10');
        preencher(linhas()[1], 'Azul M', '5');
        preencher(linhas()[2], '', '99'); // sem nome não conta

        expect([estoque.readOnly, estoque.value]).toEqual([true, '15']);
    });

    test('a lixeira tira a linha e o estoque volta a ser editável sem variações', () => {
        const { estoque, linhas } = montar({ linhas: 1, maximo: 1 });
        preencher(linhas()[0], 'Azul P', '10');
        const adicionar = document.querySelector('[data-adicionar-variacao]');
        expect(adicionar.disabled).toBe(true);

        linhas()[0].querySelector('[data-remover-variacao] svg').dispatchEvent(new Event('click', { bubbles: true }));

        expect(linhas()).toHaveLength(0);
        expect(estoque.readOnly).toBe(false);
        expect(adicionar.disabled).toBe(false);
    });

    test('clique fora da lixeira não tira nada', () => {
        const { linhas } = montar({ linhas: 1 });
        linhas()[0].querySelector('[name="variacao_nome"]').dispatchEvent(new Event('click', { bubbles: true }));
        expect(linhas()).toHaveLength(1);
    });

    test('a unidade define o passo das quantidades e "sem controle" esconde as quantidades', () => {
        const { linhas } = montar({ linhas: 1 });
        const quantidade = linhas()[0].querySelector('[name="variacao_quantidade"]');
        expect(quantidade.step).toBe('1');

        const unidade = document.querySelector('[name="unidade"]');
        unidade.value = 'kg';
        unidade.dispatchEvent(new Event('change', { bubbles: true }));
        expect(quantidade.step).toBe('0.001');

        const semControle = document.querySelector('[name="sem_controle_de_estoque"]');
        const bloco = linhas()[0].querySelector('[data-quantidade-da-variacao]');
        expect(bloco.classList.contains('hidden')).toBe(false);
        semControle.checked = true;
        semControle.dispatchEvent(new Event('change', { bubbles: true }));
        expect(bloco.classList.contains('hidden')).toBe(true);
    });

    test('liga sozinho quando a página carrega', () => {
        montar({ linhas: 0 });
        const html = document.body.innerHTML;
        document.body.innerHTML = html; // a mesma marcação, ainda sem ligar
        document.dispatchEvent(new Event('DOMContentLoaded'));
        document.querySelector('[data-adicionar-variacao]').click();
        expect(document.querySelectorAll('[data-lista-variacoes] [data-variacao-produto]')).toHaveLength(1);
    });
});

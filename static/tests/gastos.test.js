/**
 * @jest-environment jsdom
 */
const { subtotalDaCompra, totalDaCompra, iniciarCompra } = require('../js/gastos.js');

const LINHA = `
    <li data-item-compra>
        <select name="item_produto" data-produto-compra>
            <option value="">Escolha</option>
            <option value="1" data-custo="12.5" data-sigla="un." data-casas="0">Bolo</option>
            <option value="2" data-custo="39.9" data-sigla="kg" data-casas="3">Queijo</option>
            <option value="3" data-custo="0" data-sigla="un." data-casas="0">Brinde</option>
        </select>
        <input name="item_quantidade"><span data-sigla-compra>un.</span>
        <input name="item_custo">
        <button type="button" data-remover-item-compra><span>x</span></button>
    </li>`;

function montar() {
    document.body.innerHTML = `
        <form data-compra>
            <ol data-itens-compra>${LINHA}</ol>
            <template data-modelo-item-compra>${LINHA}</template>
            <button type="button" data-adicionar-item-compra></button>
            <strong data-total-compra></strong>
        </form>`;
    const formulario = document.querySelector('form');
    iniciarCompra(formulario);
    const linhas = () => [...formulario.querySelectorAll('[data-itens-compra] [data-item-compra]')];
    const escolher = (linha, valor) => {
        const select = linha.querySelector('select');
        select.value = valor;
        select.dispatchEvent(new Event('change'));
    };
    const digitar = (linha, nome, valor) => {
        const campo = linha.querySelector(`[name="${nome}"]`);
        campo.value = valor;
        campo.dispatchEvent(new Event('input'));
    };
    const total = () => formulario.querySelector('[data-total-compra]').textContent;
    return { formulario, linhas, escolher, digitar, total };
}

const reais = (valor) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);

test('subtotal em centavos como o servidor', () => {
    expect(subtotalDaCompra(0.35, 39.9)).toBe(13.97);
    expect(subtotalDaCompra(3, 12.5)).toBe(37.5);
});

test('escolher o produto sugere o custo e a unidade, sem apagar o que foi digitado', () => {
    const tela = montar();
    const [linha] = tela.linhas();
    tela.escolher(linha, '2');
    expect(linha.querySelector('[name="item_custo"]').value).toBe('39.9');
    expect(linha.querySelector('[data-sigla-compra]').textContent).toBe('kg');
    expect(linha.querySelector('[name="item_quantidade"]').step).toBe('0.001');
    expect(linha.querySelector('[name="item_quantidade"]').min).toBe('0.001');

    tela.digitar(linha, 'item_custo', '35');
    tela.escolher(linha, '1');
    expect(linha.querySelector('[name="item_custo"]').value).toBe('35');
    expect(linha.querySelector('[name="item_quantidade"]').step).toBe('1');
    expect(linha.querySelector('[name="item_quantidade"]').min).toBe('1');

    tela.escolher(linha, '');
    expect(linha.querySelector('[data-sigla-compra]').textContent).toBe('un.');
});

test('produto sem custo cadastrado não sugere nada', () => {
    const tela = montar();
    const [linha] = tela.linhas();
    tela.escolher(linha, '3');
    expect(linha.querySelector('[name="item_custo"]').value).toBe('');
});

test('outro produto adiciona linha e o total soma todas', () => {
    const tela = montar();
    expect(tela.total()).toBe(reais(0));
    tela.digitar(tela.linhas()[0], 'item_quantidade', '3');
    tela.digitar(tela.linhas()[0], 'item_custo', '12.5');

    tela.formulario.querySelector('[data-adicionar-item-compra]').click();
    const nova = tela.linhas()[1];
    expect(document.activeElement).toBe(nova.querySelector('select'));
    tela.escolher(nova, '2');
    tela.digitar(nova, 'item_quantidade', '0.35');

    expect(tela.total()).toBe(reais(51.47));
    expect(totalDaCompra(tela.formulario)).toBeCloseTo(51.47);
});

test('a lixeira tira a linha; a última só é limpa', () => {
    const tela = montar();
    tela.formulario.querySelector('[data-adicionar-item-compra]').click();
    tela.digitar(tela.linhas()[0], 'item_quantidade', '2');
    tela.digitar(tela.linhas()[0], 'item_custo', '10');

    tela.linhas()[1].querySelector('[data-remover-item-compra] span').click();
    expect(tela.linhas()).toHaveLength(1);
    expect(tela.total()).toBe(reais(20));

    tela.linhas()[0].querySelector('[data-remover-item-compra]').click();
    expect(tela.linhas()).toHaveLength(1);
    expect(tela.linhas()[0].querySelector('[name="item_quantidade"]').value).toBe('');
    expect(tela.total()).toBe(reais(0));

    tela.formulario.querySelector('[data-itens-compra]').click(); // clique fora da lixeira não faz nada
    expect(tela.linhas()).toHaveLength(1);
});

test('liga sozinho ao carregar a página', () => {
    document.body.innerHTML = `<form data-compra><ol data-itens-compra>${LINHA}</ol><template data-modelo-item-compra>${LINHA}</template>
        <button type="button" data-adicionar-item-compra></button><strong data-total-compra></strong></form>`;
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('[data-total-compra]').textContent).toBe(reais(0));
});

test('digitar o custo por último já atualiza o total; a opção vazia volta o passo para 1', () => {
    const tela = montar();
    const linha = tela.linhas()[0];
    tela.escolher(linha, '2');
    tela.digitar(linha, 'item_quantidade', '2');
    tela.digitar(linha, 'item_custo', '10');
    expect(tela.total()).toBe(reais(20));

    tela.escolher(linha, '');
    expect(linha.querySelector('[name="item_quantidade"]').step).toBe('1');
});

/**
 * @jest-environment jsdom
 */

describe('Testes de Cobertura Total - main.js', () => {

    beforeEach(() => {
        jest.resetModules();
    });

    test('1. Deve disparar DOMContentLoaded com IDs padrão (id_)', () => {
        document.body.innerHTML = `
            <input id="id_preco_custo" value="100" />
            <input id="id_margem_lucro" value="50" />
            <input id="id_preco_venda" value="150" />
            <input />
        `;
        jest.useFakeTimers();
        window.HTMLElement.prototype.scrollIntoView = jest.fn();

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        const input = document.querySelector('input');
        input.dispatchEvent(new Event('focus'));

        jest.advanceTimersByTime(300);
        expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();

        const margem = document.getElementById('id_margem_lucro');
        margem.value = '20';
        margem.dispatchEvent(new Event('input'));
        expect(document.getElementById('id_preco_venda').value).toBe('120.00');

        const venda = document.getElementById('id_preco_venda');
        venda.value = '200';
        venda.dispatchEvent(new Event('input'));
        expect(margem.value).toBe('100.00');

        jest.useRealTimers();
    });

    test('2. Deve testar IDs alternativos (edit-) forçando o lado direito do OR', () => {
        document.body.innerHTML = `
            <input id="edit-preco-custo" value="100" />
            <input id="edit-margem-lucro" value="50" />
            <input id="edit-preco-venda" value="150" />
        `;

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        const margem = document.getElementById('edit-margem-lucro');
        margem.value = '10';
        margem.dispatchEvent(new Event('input'));
        expect(document.getElementById('id_preco_venda') || document.getElementById('edit-preco-venda').value).toBe('110.00');

        const venda = document.getElementById('edit-preco-venda');
        venda.value = '200';
        venda.dispatchEvent(new Event('input'));
        expect(margem.value).toBe('100.00');
    });

    test('3. Cobre todas as validações de custo <= 0, margem/venda vazias e ramos lógicos', () => {
        document.body.innerHTML = `
            <input id="id_preco_custo" value="0" />
            <input id="id_margem_lucro" value="" />
            <input id="id_preco_venda" value="" />
        `;

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        const margem = document.getElementById('id_margem_lucro');
        const venda = document.getElementById('id_preco_venda');
        const custo = document.getElementById('id_preco_custo');

        margem.value = '20';
        margem.dispatchEvent(new Event('input'));

        custo.value = '100';
        margem.value = '';
        margem.dispatchEvent(new Event('input'));

        custo.value = '0';
        venda.value = '';
        venda.dispatchEvent(new Event('input'));

        custo.value = '100';
        venda.value = '120';
        venda.dispatchEvent(new Event('input'));
        expect(venda.value).toBe('120');
    });

    test('3.1. Deve testar o ramo falso de if (margemInput) (Linha 17)', () => {
        document.body.innerHTML = `
            <input id="id_preco_custo" value="100" />
            <input id="id_preco_venda" value="150" />
        `;

        require('../js/main.js');
        expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
        
        const venda = document.getElementById('id_preco_venda');
        venda.value = '200';
        expect(() => venda.dispatchEvent(new Event('input'))).not.toThrow();
    });

    test('4. Deve testar select com poucas opções (< 2)', () => {
        document.body.innerHTML = `
            <select id="select-categoria">
                <option value="__novo__">Nova</option>
            </select>
            <input id="input-nova-categoria" class="hidden" />
        `;

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));
        const inputNova = document.getElementById('input-nova-categoria');
        expect(inputNova.classList.contains('hidden')).toBeFalsy();
    });

    test('5. Deve testar funções unitárias (tratarMudancaCategoria, marcarParaRemover, modais)', () => {
        const { 
            tratarMudancaCategoria, 
            marcarParaRemover, 
            abrirModalEdicaoCliente, 
            fecharModalEdicaoCliente 
        } = require('../js/main.js');

        const select = document.createElement('select');
        select.innerHTML = '<option value="geral">Geral</option><option value="__novo__">Novo</option>';
        select.value = 'geral';
        const inputNova = document.createElement('input');
        inputNova.id = 'input-nova-categoria';
        document.body.appendChild(select);
        document.body.appendChild(inputNova);

        tratarMudancaCategoria(select);
        expect(select.getAttribute('name')).toBe('categoria');

        select.value = '__novo__';
        tratarMudancaCategoria(select);
        expect(select.hasAttribute('name')).toBeFalsy();

        jest.useFakeTimers();
        const inputRemover = document.createElement('input');
        inputRemover.id = 'remover_imagens';
        document.body.appendChild(inputRemover);
        const wrapper = document.createElement('div');

        marcarParaRemover('10', wrapper);
        marcarParaRemover('10', wrapper); // testa if já existente
        expect(inputRemover.value).toBe('10');
        
        jest.advanceTimersByTime(300);
        jest.useRealTimers();

        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        expect(() => fecharModalEdicaoCliente()).not.toThrow();

        document.body.innerHTML = `
            <div id="modal-edicao-cliente"></div>
            <form id="form-edicao-cliente"></form>
            <input id="edit-cli-nome" />
            <input id="edit-cli-telefone" />
            <input id="edit-cli-email" />
            <input id="edit-cli-endereco" />
        `;
        abrirModalEdicaoCliente('1', 'Nome', 'Tel', 'Email', 'End');
        fecharModalEdicaoCliente();

        document.body.innerHTML = '<div id="modal-edicao-cliente"></div>';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();

        document.body.innerHTML = '<form id="form-edicao-cliente"></form>';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        
        document.body.innerHTML = '';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        expect(() => fecharModalEdicaoCliente()).not.toThrow();
        expect(() => tratarMudancaCategoria({ value: '__novo__' })).not.toThrow();
    });

    test('6. Deve testar o bloco de exportação CommonJS quando module for undefined', () => {
        const originalModule = global.module;
        
        Object.defineProperty(global, 'module', {
            value: undefined,
            configurable: true,
            writable: true
        });

        jest.resetModules();
        expect(() => require('../js/main.js')).not.toThrow();

        Object.defineProperty(global, 'module', {
            value: originalModule,
            configurable: true,
            writable: true
        });
    });

});
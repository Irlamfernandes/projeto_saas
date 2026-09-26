/**
 * @jest-environment jsdom
 */

describe('Testes de Cobertura Total - main.js', () => {

    beforeEach(() => {
        jest.resetModules();
        document.body.innerHTML = '';
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
        window.matchMedia = jest.fn(() => ({ matches: true })); // tela de toque

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
        delete window.matchMedia;
    });

    test('1b. No computador, focar um campo não rola a página', () => {
        document.body.innerHTML = '<input />';
        jest.useFakeTimers();
        window.HTMLElement.prototype.scrollIntoView = jest.fn();
        window.matchMedia = jest.fn(() => ({ matches: false }));

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));
        document.querySelector('input').dispatchEvent(new Event('focus'));
        jest.advanceTimersByTime(300);

        expect(window.HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
        jest.useRealTimers();
        delete window.matchMedia;
    });

    test('1c. Na edição, calcula o lucro ao abrir quando ele está zerado', () => {
        document.body.innerHTML = `
            <input id="id_preco_custo" value="8.10" />
            <input id="id_margem_lucro" value="0.00" />
            <input id="id_preco_venda" value="15.50" />
        `;
        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        expect(document.getElementById('id_margem_lucro').value).toBe('91.36');
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
        expect(document.getElementById('edit-preco-venda').value).toBe('110.00');

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

    test('3.1. Deve testar o ramo falso de if (margemInput) e early return da calculadora', () => {
        document.body.innerHTML = `
            <input id="id_preco_custo" value="100" />
            <input id="id_preco_venda" value="150" />
        `;

        require('../js/main.js');
        expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
        
        const venda = document.getElementById('id_preco_venda');
        venda.value = '200';
        expect(() => venda.dispatchEvent(new Event('input'))).not.toThrow();

        document.body.innerHTML = '';
        expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
    });

    test('4. Deve testar select com poucas opções (<= 2)', () => {
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
        // Regressão: o campo de nova categoria (vazio) também se chamava "categoria" e sobrescrevia a escolha
        expect(inputNova.hasAttribute('name')).toBeFalsy();

        select.value = '__novo__';
        tratarMudancaCategoria(select);
        expect(select.hasAttribute('name')).toBeFalsy();
        expect(inputNova.getAttribute('name')).toBe('categoria');

        jest.useFakeTimers();
        const inputRemover = document.createElement('input');
        inputRemover.id = 'remover_imagens';
        document.body.appendChild(inputRemover);
        const wrapper = document.createElement('div');

        marcarParaRemover('10', wrapper);
        marcarParaRemover('10', wrapper);
        expect(inputRemover.value).toBe('10');
        
        jest.advanceTimersByTime(300);
        jest.useRealTimers();

        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        expect(() => fecharModalEdicaoCliente()).not.toThrow();

        document.body.innerHTML = `
            <dialog id="modal-edicao-cliente"></dialog>
            <form id="form-edicao-cliente"></form>
            <input id="edit-cli-nome" />
            <input id="edit-cli-telefone" />
            <input id="edit-cli-email" />
            <input id="edit-cli-endereco" />
        `;
        const modal = document.getElementById('modal-edicao-cliente');
        modal.showModal = jest.fn();
        modal.close = jest.fn();

        abrirModalEdicaoCliente('1', 'Nome', 'Tel', 'Email', 'End');
        expect(modal.showModal).toHaveBeenCalled();

        fecharModalEdicaoCliente();
        expect(modal.close).toHaveBeenCalled();

        delete modal.showModal;
        expect(() => abrirModalEdicaoCliente('1', 'Nome', 'Tel', 'Email', 'End')).not.toThrow();

        document.body.innerHTML = '<div id="modal-edicao-cliente"></div>';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();

        document.body.innerHTML = '<form id="form-edicao-cliente"></form>';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        
        document.body.innerHTML = '';
        expect(() => abrirModalEdicaoCliente('1', 'a', 'b', 'c', 'd')).not.toThrow();
        expect(() => fecharModalEdicaoCliente()).not.toThrow();
        expect(() => tratarMudancaCategoria({ value: '__novo__' })).not.toThrow();
    });

    test('6. Deve testar fechar modal ao clicar fora (inicializarFecharModalAoClicarFora)', () => {
        document.body.innerHTML = `<dialog id="modal-edicao-cliente"></dialog>`;
        const modal = document.getElementById('modal-edicao-cliente');
        modal.close = jest.fn();
        modal.getBoundingClientRect = jest.fn(() => ({
            top: 100,
            left: 100,
            width: 200,
            height: 200
        }));

        require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        modal.dispatchEvent(new MouseEvent('click', { clientX: 150, clientY: 150 }));
        expect(modal.close).not.toHaveBeenCalled();

        modal.dispatchEvent(new MouseEvent('click', { clientX: 50, clientY: 50 }));
        expect(modal.close).toHaveBeenCalled();

        delete modal.close;
        modal.dispatchEvent(new MouseEvent('click', { clientX: 50, clientY: 50 }));
    });

    test('7. Deve testar modal de galeria, atalhos de teclado e navegação', () => {
        document.body.innerHTML = `
            <div id="modal-imagem" class="hidden">
                <img id="modal-imagem-src" />
                <span id="modal-indicador"></span>
                <button id="btn-anterior"></button>
                <button id="btn-proximo"></button>
            </div>
        `;

        const { abrirModalGaleria, mudarImagem, fecharModalDireto } = require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        const modal = document.getElementById('modal-imagem');
        const img = document.getElementById('modal-imagem-src');
        const indicador = document.getElementById('modal-indicador');
        const btnAnt = document.getElementById('btn-anterior');
        const btnProx = document.getElementById('btn-proximo');

        abrirModalGaleria([]);
        abrirModalGaleria(null);
        expect(modal.classList.contains('hidden')).toBeTruthy();

        abrirModalGaleria(['foto1.jpg']);
        expect(btnAnt.style.display).toBe('none');
        expect(btnProx.style.display).toBe('none');

        const imagens = ['img1.jpg', 'img2.jpg', 'img3.jpg'];
        abrirModalGaleria(imagens, 0);

        expect(btnAnt.style.display).toBe('');
        expect(btnProx.style.display).toBe('');
        expect(modal.classList.contains('hidden')).toBeFalsy();
        expect(img.src).toContain('img1.jpg');
        expect(indicador.textContent).toBe('1 de 3');

        mudarImagem(1);
        expect(img.src).toContain('img2.jpg');
        mudarImagem(1);
        expect(img.src).toContain('img3.jpg');
        mudarImagem(1);
        expect(img.src).toContain('img1.jpg');
        mudarImagem(-1);
        expect(img.src).toContain('img3.jpg');

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
        expect(img.src).toContain('img2.jpg');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
        expect(img.src).toContain('img3.jpg');
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(modal.classList.contains('hidden')).toBeTruthy();

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));

        abrirModalGaleria(imagens, 0);
        img.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(modal.classList.contains('hidden')).toBeFalsy();

        modal.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(modal.classList.contains('hidden')).toBeTruthy();

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        fecharModalDireto();
        expect(modal.classList.contains('hidden')).toBeTruthy();
        expect(modal.classList.contains('flex')).toBeFalsy();
    });

    test('8. Deve testar galeria sem elementos de exibição no DOM (cobertura total de atualizarExibicaoGaleria)', () => {
        document.body.innerHTML = `
            <div id="modal-imagem" class="hidden"></div>
        `;

        const { abrirModalGaleria, mudarImagem, fecharModalDireto } = require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        abrirModalGaleria(['img1.jpg']);
        mudarImagem(1);

        abrirModalGaleria(['img1.jpg', 'img2.jpg']);
        expect(() => mudarImagem(1)).not.toThrow();

        document.body.innerHTML = '';
        expect(() => abrirModalGaleria(['img1.jpg'])).not.toThrow();
        expect(() => fecharModalDireto()).not.toThrow();
    });
});
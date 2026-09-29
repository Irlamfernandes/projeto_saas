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
        // Regressão: loja sem categorias não conseguia salvar produto (campo virava obrigatório)
        expect(inputNova.required).toBeFalsy();
        expect(document.activeElement).not.toBe(inputNova);
    });

    test('5. Deve testar funções unitárias (tratarMudancaCategoria, marcarParaRemover, modais)', () => {
        const { tratarMudancaCategoria, marcarParaRemover, abrirModalEdicaoCliente } = require('../js/main.js');

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
        expect(inputNova.required).toBeFalsy();
        expect(document.activeElement).toBe(inputNova);

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

        const botao = document.createElement('button');
        Object.assign(botao.dataset, { editarCliente: '/clientes/editar/7/', nome: 'Ana', telefone: 'Tel', email: 'Email', endereco: 'End' });
        expect(() => abrirModalEdicaoCliente(botao)).not.toThrow(); // página sem a janela

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

        abrirModalEdicaoCliente(botao);
        expect(modal.showModal).toHaveBeenCalled();
        expect(document.getElementById('form-edicao-cliente').getAttribute('action')).toBe('/clientes/editar/7/');
        expect(document.getElementById('edit-cli-nome').value).toBe('Ana');
        expect(document.getElementById('edit-cli-telefone').value).toBe('Tel');
        expect(document.getElementById('edit-cli-email').value).toBe('Email');
        expect(document.getElementById('edit-cli-endereco').value).toBe('End');

        document.body.innerHTML = '<dialog id="modal-edicao-cliente"></dialog>';
        expect(() => abrirModalEdicaoCliente(botao)).not.toThrow(); // sem o formulário
        expect(() => tratarMudancaCategoria({ value: '__novo__' })).not.toThrow();
    });

    describe('ações descritas em data-* (sem onclick no HTML)', () => {
        const ligar = (html) => {
            document.body.innerHTML = html;
            require('../js/main.js').inicializarAcoes();
        };

        test('categoria, limite de fotos e remover foto', () => {
            ligar(`
                <select id="select-categoria"><option value="a">A</option><option value="__novo__">Nova</option></select>
                <input id="input-nova-categoria" class="hidden">
                <input type="file" data-maximo-fotos="5">
                <input id="remover_imagens" value="">
                <div id="container-imagens-atuais"><div data-id="9"><button data-remover-foto="9"></button></div></div>`);
            const select = document.getElementById('select-categoria');
            select.value = '__novo__';
            select.dispatchEvent(new Event('change'));
            expect(document.getElementById('input-nova-categoria').getAttribute('name')).toBe('categoria');

            const fotos = document.querySelector('input[type=file]');
            fotos.setCustomValidity = jest.fn();
            fotos.dispatchEvent(new Event('change'));
            expect(fotos.setCustomValidity).toHaveBeenCalledWith('');

            document.querySelector('[data-remover-foto]').click();
            expect(document.getElementById('remover_imagens').value).toBe('9');
        });

        test('editar cliente abre a janela com os dados do botão', () => {
            ligar(`
                <button data-editar-cliente="/clientes/editar/3/" data-nome="Bia" data-telefone="" data-email="" data-endereco=""></button>
                <dialog id="modal-edicao-cliente"></dialog><form id="form-edicao-cliente"></form>
                <input id="edit-cli-nome"><input id="edit-cli-telefone"><input id="edit-cli-email"><input id="edit-cli-endereco">`);
            document.getElementById('modal-edicao-cliente').showModal = jest.fn();
            document.querySelector('[data-editar-cliente]').click();
            expect(document.getElementById('edit-cli-nome').value).toBe('Bia');
        });

        test('galeria abre com as fotos do botão e as setas trocam', () => {
            ligar(`
                <button data-galeria="a.webp b.webp "></button>
                <dialog id="modal-imagem"><img id="modal-imagem-src"><span id="modal-indicador"></span>
                <button data-mudar-foto="1"></button><button data-mudar-foto="-1"></button></dialog>`);
            simularDialogo(document.getElementById('modal-imagem'));
            document.querySelector('[data-galeria]').click();
            expect(document.getElementById('modal-indicador').textContent).toBe('1 de 2');
            document.querySelector('[data-mudar-foto="1"]').click();
            expect(document.getElementById('modal-imagem-src').src).toContain('b.webp');
            document.querySelector('[data-mudar-foto="-1"]').click();
            expect(document.getElementById('modal-imagem-src').src).toContain('a.webp');
        });

        test('formulário com data-confirmar só envia se a pessoa confirmar', () => {
            ligar('<form data-confirmar="Remover a marca da loja?"></form>');
            const form = document.querySelector('form');
            const enviar = () => {
                const evento = new Event('submit', { cancelable: true });
                form.dispatchEvent(evento);
                return evento.defaultPrevented;
            };
            window.confirm = jest.fn(() => false);
            expect(enviar()).toBe(true);
            expect(window.confirm).toHaveBeenCalledWith('Remover a marca da loja?');
            window.confirm = jest.fn(() => true);
            expect(enviar()).toBe(false);
            delete window.confirm;
        });
    });

    /* O jsdom não abre <dialog> de verdade: showModal/close só ligam e desligam o atributo "open". */
    function simularDialogo(dialogo) {
        dialogo.showModal = jest.fn(() => { dialogo.open = true; });
        dialogo.close = jest.fn(() => { dialogo.open = false; });
        return dialogo;
    }

    test('7. Deve testar modal de galeria, atalhos de teclado e navegação', () => {
        document.body.innerHTML = `
            <dialog id="modal-imagem">
                <img id="modal-imagem-src" />
                <span id="modal-indicador"></span>
                <button id="btn-anterior"></button>
                <button id="btn-proximo"></button>
            </dialog>
        `;
        const modal = simularDialogo(document.getElementById('modal-imagem'));

        const { abrirModalGaleria, mudarImagem, fecharModalDireto } = require('../js/main.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));

        const img = document.getElementById('modal-imagem-src');
        const indicador = document.getElementById('modal-indicador');
        const btnAnt = document.getElementById('btn-anterior');
        const btnProx = document.getElementById('btn-proximo');

        abrirModalGaleria([]);
        abrirModalGaleria(null);
        expect(modal.open).toBeFalsy();

        abrirModalGaleria(['foto1.jpg']);
        expect(btnAnt.style.display).toBe('none');
        expect(btnProx.style.display).toBe('none');

        const imagens = ['img1.jpg', 'img2.jpg', 'img3.jpg'];
        modal.showModal.mockClear();
        abrirModalGaleria(imagens, 0); // já aberta: só troca as fotos
        expect(modal.showModal).not.toHaveBeenCalled();

        expect(btnAnt.style.display).toBe('');
        expect(btnProx.style.display).toBe('');
        expect(modal.open).toBeTruthy();
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
        expect(img.src).toContain('img3.jpg');

        img.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(modal.open).toBeTruthy();

        modal.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(modal.open).toBeFalsy();

        // Fechada, as setas não mexem nas fotos
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
        expect(img.src).toContain('img3.jpg');

        abrirModalGaleria(imagens, 0);
        expect(modal.open).toBeTruthy();
        fecharModalDireto();
        expect(modal.open).toBeFalsy();
    });

    test('8. Deve testar galeria sem elementos de exibição no DOM (cobertura total de atualizarExibicaoGaleria)', () => {
        document.body.innerHTML = `
            <dialog id="modal-imagem"></dialog>
        `;
        simularDialogo(document.getElementById('modal-imagem'));

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

    describe('limitarFotos', () => {
        const montar = (fotosAtuais, removidas = '') => {
            document.body.innerHTML = `
                <input id="remover_imagens" value="${removidas}">
                <div id="container-imagens-atuais">${fotosAtuais.map((id) => `<div data-id="${id}"></div>`).join('')}</div>
                <input type="file" id="fotos" data-maximo-fotos="5">`;
            const input = document.getElementById('fotos');
            input.reportValidity = jest.fn();
            return input;
        };
        const escolher = (input, quantidade) => Object.defineProperty(input, 'files', { value: { length: quantidade }, configurable: true });

        test('aceita escolher até completar 5 fotos', () => {
            const { limitarFotos } = require('../js/main.js');
            const input = montar(['1', '2']);
            escolher(input, 3);
            limitarFotos(input);
            expect(input.validationMessage).toBe('');
            expect(input.reportValidity).not.toHaveBeenCalled();
        });

        test('avisa quantas ainda cabem quando passa do limite', () => {
            const { limitarFotos } = require('../js/main.js');
            const input = montar(['1', '2']);
            escolher(input, 4);
            limitarFotos(input);
            expect(input.validationMessage).toBe('Cada produto pode ter no máximo 5 fotos. Dá para adicionar mais 3.');
            expect(input.reportValidity).toHaveBeenCalled();
        });

        test('produto cheio pede para remover antes', () => {
            const { limitarFotos } = require('../js/main.js');
            const input = montar(['1', '2', '3', '4', '5']);
            escolher(input, 1);
            limitarFotos(input);
            expect(input.validationMessage).toBe('Cada produto pode ter no máximo 5 fotos. Remova alguma antes de adicionar outra.');
        });

        test('fotos marcadas para remover liberam espaço, inclusive depois de escolher', () => {
            const { limitarFotos, marcarParaRemover } = require('../js/main.js');
            const input = montar(['1', '2', '3', '4', '5']);
            escolher(input, 1);
            limitarFotos(input);
            expect(input.validationMessage).not.toBe('');

            marcarParaRemover('3', document.querySelector('[data-id="3"]'));
            expect(input.validationMessage).toBe('');
        });

        test('no cadastro (sem fotos atuais) o limite é 5', () => {
            const { limitarFotos } = require('../js/main.js');
            document.body.innerHTML = '<input type="file" id="fotos" data-maximo-fotos="5">';
            const input = document.getElementById('fotos');
            input.reportValidity = jest.fn();
            escolher(input, 6);
            limitarFotos(input);
            expect(input.validationMessage).toBe('Cada produto pode ter no máximo 5 fotos. Dá para adicionar mais 5.');
        });
    });

    describe('janelas de ajuda', () => {
        const montar = () => {
            document.body.innerHTML = `
                <button id="abrir" data-abrir-dialogo="ajuda"></button>
                <button id="abrir-sem-janela" data-abrir-dialogo="nao-existe"></button>
                <dialog id="ajuda" data-fechar-fora><div id="conteudo"><button id="fechar" data-fechar-dialogo></button></div></dialog>`;
            const dialogo = document.getElementById('ajuda');
            dialogo.showModal = jest.fn();
            dialogo.close = jest.fn();
            require('../js/main.js').inicializarDialogos();
            return dialogo;
        };

        test('o botão "?" abre a janela e o "fechar" fecha', () => {
            const dialogo = montar();
            document.getElementById('abrir').click();
            expect(dialogo.showModal).toHaveBeenCalled();
            document.getElementById('fechar').click();
            expect(dialogo.close).toHaveBeenCalledTimes(1);
        });

        test('toque fora da janela fecha; toque no conteúdo não', () => {
            const dialogo = montar();
            document.getElementById('conteudo').click();
            expect(dialogo.close).not.toHaveBeenCalled();
            dialogo.click();
            expect(dialogo.close).toHaveBeenCalledTimes(1);
        });

        test('botão apontando para janela que não existe não quebra a página', () => {
            montar();
            expect(() => document.getElementById('abrir-sem-janela').click()).not.toThrow();
        });

        test('é ligado sozinho quando a página carrega', () => {
            const dialogo = montar();
            jest.resetModules();
            document.body.innerHTML = '';
            document.body.appendChild(dialogo);
            const botao = document.createElement('button');
            botao.dataset.abrirDialogo = 'ajuda';
            document.body.appendChild(botao);
            require('../js/main.js');
            document.dispatchEvent(new Event('DOMContentLoaded'));
            botao.click();
            expect(dialogo.showModal).toHaveBeenCalled();
        });
    });

    describe('formulário que salva ao mudar (aparência)', () => {
        test('escolher uma opção envia o formulário', () => {
            document.body.innerHTML = `
                <form data-enviar-ao-mudar><input type="radio" name="tema" value="escuro"></form>`;
            const form = document.querySelector('form');
            form.requestSubmit = jest.fn();
            require('../js/main.js').inicializarEnvioAoMudar();

            const opcao = form.querySelector('input');
            opcao.checked = true;
            opcao.dispatchEvent(new Event('change', { bubbles: true }));

            expect(form.requestSubmit).toHaveBeenCalled();
        });
    });

    describe('marca da loja que não carrega', () => {
        const montar = () => {
            document.body.innerHTML = `
                <img data-marca-loja src="marca.webp"><span class="hidden">PP</span>
                <img data-marca-loja src="sem-iniciais.webp">`;
            return [...document.querySelectorAll('img')];
        };

        test('se a imagem falhar depois, troca pelas iniciais', () => {
            const [imagem, sozinha] = montar();
            require('../js/main.js').inicializarMarcaDaLoja();

            imagem.dispatchEvent(new Event('error'));
            expect(imagem.classList.contains('hidden')).toBe(true);
            expect(document.querySelector('span').classList.contains('hidden')).toBe(false);
            expect(() => sozinha.dispatchEvent(new Event('error'))).not.toThrow();
        });

        test('se já tinha falhado antes do script, troca na hora', () => {
            const [imagem] = montar();
            Object.defineProperty(imagem, 'complete', { value: true });
            Object.defineProperty(imagem, 'naturalWidth', { value: 0 });
            require('../js/main.js').inicializarMarcaDaLoja();
            expect(imagem.classList.contains('hidden')).toBe(true);
        });

        test('imagem que carregou fica como está', () => {
            const [imagem] = montar();
            Object.defineProperty(imagem, 'complete', { value: true });
            Object.defineProperty(imagem, 'naturalWidth', { value: 512 });
            require('../js/main.js').inicializarMarcaDaLoja();
            expect(imagem.classList.contains('hidden')).toBe(false);
        });
    });

    describe('regras finas (achadas pelo teste de mutação)', () => {
        const calculadora = (custo, margem, venda) => {
            document.body.innerHTML = `
                <input id="id_preco_custo" value="${custo}">
                <input id="id_margem_lucro" value="${margem}">
                <input id="id_preco_venda" value="${venda}">`;
            require('../js/main.js');
            document.dispatchEvent(new Event('DOMContentLoaded'));
            const campo = (id) => document.getElementById(id);
            const digitar = (id, valor) => { campo(id).value = valor; campo(id).dispatchEvent(new Event('input')); };
            return { campo, digitar };
        };

        test('lucro já preenchido não é recalculado ao abrir', () => {
            const { campo } = calculadora('100', '30', '150');
            expect(campo('id_margem_lucro').value).toBe('30');
        });

        test('preço igual ao custo dá lucro zero', () => {
            const { campo, digitar } = calculadora('100', '30', '130');
            digitar('id_preco_venda', '100');
            expect(campo('id_margem_lucro').value).toBe('0.00');
        });

        test('sem custo, não calcula preço nem lucro', () => {
            const { campo, digitar } = calculadora('0', '10', '50');
            digitar('id_margem_lucro', '40');
            expect(campo('id_preco_venda').value).toBe('50');
            digitar('id_preco_venda', '80');
            expect(campo('id_margem_lucro').value).toBe('40');
        });

        test('página só com o campo de custo não quebra', () => {
            document.body.innerHTML = '<input id="id_preco_custo" value="10">';
            require('../js/main.js');
            expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
        });

        test('categoria nova só abre sozinha quando a loja não tem categorias', () => {
            const montar = (opcoes) => {
                jest.resetModules();
                document.body.innerHTML = `<select id="select-categoria">${opcoes}</select><input id="input-nova-categoria" class="hidden">`;
                require('../js/main.js');
                document.dispatchEvent(new Event('DOMContentLoaded'));
                return document.getElementById('select-categoria').value;
            };
            expect(montar('<option value="">Sem</option><option value="__novo__">Nova</option>')).toBe('__novo__');
            expect(montar('<option value="">Sem</option><option value="doces">Doces</option><option value="__novo__">Nova</option>')).toBe('');
        });

        test('galeria com uma foto não troca; voltar da segunda vai para a primeira', () => {
            document.body.innerHTML = '<dialog id="modal-imagem"><img id="modal-imagem-src"></dialog>';
            simularDialogo(document.getElementById('modal-imagem'));
            const { abrirModalGaleria, mudarImagem } = require('../js/main.js');
            const foto = () => document.getElementById('modal-imagem-src').src;

            abrirModalGaleria(['so.webp']);
            mudarImagem(1);
            expect(foto()).toContain('so.webp');

            abrirModalGaleria(['a.webp', 'b.webp', 'c.webp'], 1);
            mudarImagem(-1);
            expect(foto()).toContain('a.webp');
        });
    });
});


describe('estoque do produto', () => {
    function montar({ unidade = 'un', semControle = false } = {}) {
        document.body.innerHTML = `
            <div data-estoque-produto>
                <select name="unidade">
                    <option value="un" data-sigla="un." data-casas="0" ${unidade === 'un' ? 'selected' : ''}>Unidade</option>
                    <option value="kg" data-sigla="kg" data-casas="3" ${unidade === 'kg' ? 'selected' : ''}>Quilo</option>
                </select>
                <div data-bloco-quantidade><input name="quantidade_estoque" required><span data-sigla-do-estoque></span></div>
                <input type="checkbox" name="sem_controle_de_estoque" ${semControle ? 'checked' : ''}>
            </div>`;
        require('../js/main.js').inicializarEstoqueDoProduto(document);
        const $ = (seletor) => document.querySelector(seletor);
        const mudar = (seletor, alterar) => { alterar($(seletor)); $(seletor).dispatchEvent(new Event('change')); };
        return { $, mudar };
    }

    test('a unidade define o passo e a sigla da quantidade', () => {
        const { $, mudar } = montar();
        expect([$('[name="quantidade_estoque"]').step, $('[data-sigla-do-estoque]').textContent]).toEqual(['1', 'un.']);

        mudar('[name="unidade"]', (select) => { select.value = 'kg'; });

        expect([$('[name="quantidade_estoque"]').step, $('[data-sigla-do-estoque]').textContent]).toEqual(['0.001', 'kg']);
        // As opções da lista continuam com o próprio nome (a sigla vai só no campo de quantidade).
        expect([...document.querySelectorAll('option')].map((o) => o.textContent)).toEqual(['Unidade', 'Quilo']);
    });

    test('sem controle esconde a quantidade e ela deixa de ser obrigatória', () => {
        const { $, mudar } = montar({ unidade: 'kg', semControle: true });
        expect($('[data-bloco-quantidade]').classList.contains('hidden')).toBe(true);
        expect($('[name="quantidade_estoque"]').required).toBe(false);

        mudar('[name="sem_controle_de_estoque"]', (caixa) => { caixa.checked = false; });

        expect($('[data-bloco-quantidade]').classList.contains('hidden')).toBe(false);
        expect($('[name="quantidade_estoque"]').required).toBe(true);
    });
});

describe('opções do produto no cadastro', () => {
    const BLOCO = `<li data-opcao-produto><input name="opcao_nome"><textarea name="opcao_valores"></textarea>
        <button type="button" data-remover-opcao><svg></svg></button></li>`;

    function montar(maximo = 3) {
        document.body.innerHTML = `
            <details data-opcoes-produto data-maximo="${maximo}">
                <ol data-lista-opcoes>${BLOCO}</ol>
                <button type="button" data-adicionar-opcao>Outra opção</button>
                <template data-modelo-opcao>${BLOCO}</template>
            </details>`;
        require('../js/main.js').inicializarOpcoesDoProduto(document);
        return {
            lista: document.querySelector('[data-lista-opcoes]'),
            adicionar: document.querySelector('[data-adicionar-opcao]'),
        };
    }

    beforeEach(() => { jest.resetModules(); });

    test('"Outra opção" copia o bloco vazio, foca o nome e para no máximo', () => {
        const { lista, adicionar } = montar(2);
        adicionar.click();

        expect(lista.children).toHaveLength(2);
        expect(document.activeElement).toBe(lista.lastElementChild.querySelector('[name="opcao_nome"]'));
        expect(adicionar.disabled).toBe(true);
    });

    test('a lixeira tira a opção; a última só é limpa', () => {
        const { lista, adicionar } = montar();
        adicionar.click();
        lista.querySelector('[name="opcao_nome"]').value = 'Tamanho';

        lista.firstElementChild.querySelector('svg').dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(lista.children).toHaveLength(1);

        const unica = lista.firstElementChild;
        unica.querySelector('[name="opcao_nome"]').value = 'Cor';
        unica.querySelector('[name="opcao_valores"]').value = 'Azul';
        unica.querySelector('[data-remover-opcao]').click();
        expect(lista.children).toHaveLength(1);
        expect([unica.querySelector('input').value, unica.querySelector('textarea').value]).toEqual(['', '']);
        expect(adicionar.disabled).toBe(false);

        lista.click(); // clique fora da lixeira não faz nada
        expect(lista.children).toHaveLength(1);
    });
});

describe('voltar depois de sair da conta', () => {
    test('página restaurada da memória é pedida de novo; carregamento normal não', () => {
        const { recarregarSeVoltouDaMemoria } = require('../js/main.js');
        const eventos = {};
        const janela = { addEventListener: (nome, funcao) => { eventos[nome] = funcao; }, location: { reload: jest.fn() } };
        recarregarSeVoltouDaMemoria(janela);

        eventos.pageshow({ persisted: false });
        expect(janela.location.reload).not.toHaveBeenCalled();
        eventos.pageshow({ persisted: true });
        expect(janela.location.reload).toHaveBeenCalledTimes(1);
    });
});

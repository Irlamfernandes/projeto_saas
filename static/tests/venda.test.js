/**
 * @jest-environment jsdom
 */
const {
    normalizar, buscarProdutos, totalDoCarrinho, formatarReais, subtotal, descreverEstoque, descreverPreco,
    iniciarCarrinho, iniciarResumoDePagamento,
    formaDePagamentoObrigatoria, iniciarFormaObrigatoria, somarDias, iniciarVencimento,
} = require('../js/venda.js');

const CATALOGO = [
    { id: 1, nome: 'Pão francês', codigo: 'P01', preco: '0.80', estoque: 100 },
    { id: 2, nome: 'Pão de queijo', codigo: 'PQ', preco: '3.50', estoque: 2 },
    { id: 3, nome: 'Café coado', codigo: '', preco: '5.00', estoque: 10 },
    { id: 4, nome: 'Bolo esgotado', codigo: 'B1', preco: '30.00', estoque: 0 },
];

function montarPagina({ itens = null, comResumo = false, catalogo = CATALOGO } = {}) {
    document.body.innerHTML = `
        <form>
            ${comResumo ? `<select name="cliente"><option value="">Balcão</option><option value="7">Ana</option></select>
            <div data-pago-agora><input name="valor_pago"></div><p data-resumo-pagamento></p>` : ''}
            <div data-carrinho data-catalogo="catalogo" ${itens ? 'data-itens="iniciais"' : ''}>
                <input id="busca-produto"><ul id="resultados-produto" class="hidden"></ul>
                <ul data-itens-lista></ul><p data-carrinho-vazio></p><strong data-total></strong>
            </div>
        </form>
        <script type="application/json" id="catalogo">${JSON.stringify(catalogo)}</script>
        ${itens ? `<script type="application/json" id="iniciais">${JSON.stringify(itens)}</script>` : ''}`;
    const raiz = document.querySelector('[data-carrinho]');
    const formulario = document.querySelector('form');
    if (comResumo) iniciarResumoDePagamento(formulario);
    const carrinho = iniciarCarrinho(raiz);
    return { raiz, formulario, carrinho, busca: document.getElementById('busca-produto'), resultados: document.getElementById('resultados-produto') };
}

function digitar(busca, texto) {
    busca.value = texto;
    busca.dispatchEvent(new Event('input'));
}

function tecla(busca, key) {
    const evento = new KeyboardEvent('keydown', { key, cancelable: true });
    busca.dispatchEvent(evento);
    return evento;
}

const enviados = () => ({
    produtos: [...document.querySelectorAll('[name="item_produto"]')].map((e) => e.value),
    quantidades: [...document.querySelectorAll('[name="item_quantidade"]')].map((e) => e.value),
});
const total = () => document.querySelector('[data-total]').textContent;

describe('funções puras', () => {
    test('normalizar ignora acentos, maiúsculas e espaços', () => {
        expect(normalizar('  Pão Francês ')).toBe('pao frances');
        expect(normalizar(undefined)).toBe('');
    });

    test('busca por nome sem acento e por código, com o código exato primeiro', () => {
        expect(buscarProdutos(CATALOGO, 'pao').map((p) => p.id)).toEqual([2, 1]);
        expect(buscarProdutos(CATALOGO, 'pq').map((p) => p.id)).toEqual([2]);
        expect(buscarProdutos(CATALOGO, 'p01').map((p) => p.id)).toEqual([1]);
        expect(buscarProdutos(CATALOGO, 'coado').map((p) => p.id)).toEqual([3]);
        expect(buscarProdutos(CATALOGO, '   ')).toEqual([]);
        expect(buscarProdutos(CATALOGO, 'a', 2)).toHaveLength(2);
    });

    test('total e formato em reais', () => {
        expect(totalDoCarrinho([{ preco: 0.8, quantidade: 3 }, { preco: 5, quantidade: 1 }])).toBeCloseTo(7.4);
        expect(formatarReais(1234.5)).toBe('R$ 1.234,50');
    });
});

describe('carrinho', () => {
    beforeEach(() => { Element.prototype.scrollIntoView = jest.fn(); });

    test('começa vazio e com total zero', () => {
        montarPagina();
        expect(document.querySelector('[data-carrinho-vazio]').classList.contains('hidden')).toBe(false);
        expect(total()).toBe('R$ 0,00');
    });

    test('a lista de sugestões vira listbox quando o script liga a busca', () => {
        const { resultados } = montarPagina();
        expect(resultados.getAttribute('role')).toBe('listbox');
    });

    test('digitar mostra os resultados com preço e estoque; Enter adiciona o primeiro', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'pao');

        expect(resultados.classList.contains('hidden')).toBe(false);
        expect(busca.getAttribute('aria-expanded')).toBe('true');
        expect(resultados.children[0].textContent).toContain('Pão de queijo');
        expect(resultados.children[0].textContent).toContain('2 em estoque');

        const evento = tecla(busca, 'Enter');
        expect(evento.defaultPrevented).toBe(true); // não envia a venda pela metade
        expect(enviados()).toEqual({ produtos: ['2'], quantidades: ['1'] });
        expect(busca.value).toBe('');
        expect(resultados.classList.contains('hidden')).toBe(true);
    });

    test('setas escolhem outro resultado e Escape fecha a lista', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'pao');
        tecla(busca, 'ArrowDown');
        expect(busca.getAttribute('aria-activedescendant')).toBe('produto-1');
        tecla(busca, 'ArrowDown');
        expect(busca.getAttribute('aria-activedescendant')).toBe('produto-2');
        tecla(busca, 'ArrowUp');
        tecla(busca, 'Enter');
        expect(enviados().produtos).toEqual(['1']);

        digitar(busca, 'cafe');
        tecla(busca, 'Escape');
        expect(resultados.classList.contains('hidden')).toBe(true);
    });

    test('clique adiciona; o mesmo produto de novo soma na quantidade, até o estoque', () => {
        const { busca } = montarPagina();
        for (let i = 0; i < 3; i += 1) {
            digitar(busca, 'pq');
            document.getElementById('produto-2').dispatchEvent(new MouseEvent('mousedown', { cancelable: true }));
        }
        expect(enviados()).toEqual({ produtos: ['2'], quantidades: ['2'] });
        expect(total()).toBe('R$ 7,00');
    });

    test('produto sem estoque aparece, mas não entra na venda', () => {
        const { busca } = montarPagina();
        digitar(busca, 'bolo');
        const opcao = document.getElementById('produto-4');
        expect(opcao.getAttribute('aria-disabled')).toBe('true');
        expect(opcao.textContent).toContain('sem estoque');
        opcao.dispatchEvent(new MouseEvent('mousedown', { cancelable: true }));
        tecla(busca, 'Enter');
        expect(enviados().produtos).toEqual([]);
    });

    test('busca sem resultado avisa; setas e Enter não fazem nada', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'xyz');
        expect(resultados.textContent).toContain('Nenhum produto');
        tecla(busca, 'ArrowDown');
        tecla(busca, 'Enter');
        expect(enviados().produtos).toEqual([]);
        digitar(busca, '');
        expect(resultados.classList.contains('hidden')).toBe(true);
    });

    test('botões de quantidade, campo digitado e remover', () => {
        const { carrinho } = montarPagina();
        carrinho.adicionar(CATALOGO[2]); // café, estoque 10
        const [menos, mais] = document.querySelectorAll('.quantidade-botao');
        expect(menos.disabled).toBe(true);
        mais.click();
        expect(enviados().quantidades).toEqual(['2']);

        const campo = document.querySelector('.quantidade-campo');
        campo.value = '50';
        campo.dispatchEvent(new Event('change'));
        expect(enviados().quantidades).toEqual(['10']); // limitado ao estoque
        expect(document.querySelectorAll('.quantidade-botao')[1].disabled).toBe(true);

        document.querySelectorAll('.quantidade-botao')[0].click();
        expect(enviados().quantidades).toEqual(['9']);

        document.querySelector('[aria-label="Tirar Café coado da venda"]').click();
        expect(enviados().produtos).toEqual([]);
    });

    test('quantidade inválida volta para 1', () => {
        const { carrinho } = montarPagina();
        carrinho.adicionar(CATALOGO[2]);
        const campo = document.querySelector('.quantidade-campo');
        campo.value = 'abc';
        campo.dispatchEvent(new Event('change'));
        expect(enviados().quantidades).toEqual(['1']);
    });

    test('na edição, começa com os itens e o preço da época', () => {
        montarPagina({ itens: [{ id: 3, quantidade: 2, preco: '4.00' }, { id: 999, quantidade: 1, preco: '1.00' }] });
        expect(enviados()).toEqual({ produtos: ['3'], quantidades: ['2'] });
        expect(total()).toBe('R$ 8,00');
        expect(document.querySelector('.item-carrinho').textContent).toContain('R$ 4,00 cada');
    });

    test('não envia venda sem itens', () => {
        const { formulario, busca, carrinho } = montarPagina();
        busca.reportValidity = jest.fn();
        const envio = new Event('submit', { cancelable: true });
        formulario.dispatchEvent(envio);
        expect(envio.defaultPrevented).toBe(true);
        expect(busca.validationMessage).toBe('Adicione pelo menos um produto à venda.');

        carrinho.adicionar(CATALOGO[0]);
        const segundo = new Event('submit', { cancelable: true });
        formulario.dispatchEvent(segundo);
        expect(segundo.defaultPrevented).toBe(false);
    });

    test('focar a busca com texto reabre os resultados; sair do campo fecha', () => {
        const { busca, resultados } = montarPagina();
        busca.value = 'cafe';
        busca.dispatchEvent(new Event('focus'));
        expect(resultados.classList.contains('hidden')).toBe(false);
        document.getElementById('produto-3').dispatchEvent(new MouseEvent('mousemove'));
        busca.dispatchEvent(new Event('blur'));
        expect(resultados.classList.contains('hidden')).toBe(true);
        busca.value = '';
        busca.dispatchEvent(new Event('focus'));
        expect(resultados.classList.contains('hidden')).toBe(true);
    });
});

describe('resumo do pagamento', () => {
    const resumo = () => document.querySelector('[data-resumo-pagamento]').textContent;

    test('balcão: pago na hora e sem campo de "pago agora"', () => {
        const { carrinho } = montarPagina({ comResumo: true });
        expect(resumo()).toBe('Venda de balcão: paga na hora.');
        carrinho.adicionar(CATALOGO[2]);
        expect(resumo()).toBe('Venda de balcão: R$ 5,00 pagos na hora.');
        expect(document.querySelector('[data-pago-agora]').classList.contains('hidden')).toBe(true);
    });

    test('com cliente: mostra o que vai para a caderneta, quitado ou crédito', () => {
        const { carrinho } = montarPagina({ comResumo: true });
        carrinho.adicionar(CATALOGO[2]);
        const cliente = document.querySelector('[name="cliente"]');
        const pago = document.querySelector('[name="valor_pago"]');
        cliente.value = '7';
        cliente.dispatchEvent(new Event('change'));
        expect(resumo()).toBe('Vai para a caderneta: R$ 5,00.');

        pago.value = '5';
        pago.dispatchEvent(new Event('input'));
        expect(resumo()).toBe('Pago por completo agora.');

        pago.value = '8';
        pago.dispatchEvent(new Event('input'));
        expect(resumo()).toBe('Sobra R$ 3,00 de crédito para o cliente.');
    });

    test('produto esgotado não entra no carrinho; outras teclas não mexem na busca', () => {
        const { carrinho, busca } = montarPagina();
        carrinho.adicionar(CATALOGO[3]);
        expect(carrinho.itens).toEqual([]);

        digitar(busca, 'pão');
        const evento = tecla(busca, 'a');
        expect(evento.defaultPrevented).toBe(false);
        expect(carrinho.itens).toEqual([]);
    });

    test('página sem os campos de pagamento não quebra', () => {
        document.body.innerHTML = '<form></form>';
        expect(() => iniciarResumoDePagamento(document.querySelector('form'))).not.toThrow();
    });
});

describe('inicialização automática', () => {
    test('liga carrinho e resumo ao carregar a página', () => {
        montarPagina({ comResumo: true });
        document.dispatchEvent(new Event('DOMContentLoaded'));
        expect(document.querySelector('[data-resumo-pagamento]').textContent).toBe('Venda de balcão: paga na hora.');
    });

    test('carrinho fora de um formulário liga só a busca', () => {
        document.body.innerHTML = `
            <div data-carrinho data-catalogo="catalogo">
                <input id="busca-produto"><ul id="resultados-produto" class="hidden"></ul>
                <ul data-itens-lista></ul><p data-carrinho-vazio></p><strong data-total></strong>
            </div>
            <script type="application/json" id="catalogo">${JSON.stringify(CATALOGO)}</script>`;
        document.dispatchEvent(new Event('DOMContentLoaded'));
        expect(document.getElementById('resultados-produto').getAttribute('role')).toBe('listbox');
    });
});

describe('forma de pagamento obrigatória', () => {
    function montarFormulario({ pagouNoAto = false } = {}) {
        document.body.innerHTML = `
            <form ${pagouNoAto ? 'data-pagou-no-ato' : ''}>
                <select name="cliente"><option value="">Balcão</option><option value="7">Ana</option></select>
                <input name="valor_pago">
                <fieldset data-forma-pagamento><legend>Como pagou <span class="obrigatorio">*</span></legend>
                    <input type="radio" name="forma_pagamento" value="pix"><input type="radio" name="forma_pagamento" value="dinheiro">
                </fieldset>
            </form>`;
        const formulario = document.querySelector('form');
        iniciarFormaObrigatoria(formulario);
        return {
            formulario,
            cliente: formulario.querySelector('[name="cliente"]'),
            pago: formulario.querySelector('[name="valor_pago"]'),
            asteriscoVisivel: () => !formulario.querySelector('.obrigatorio').classList.contains('hidden'),
            opcoesObrigatorias: () => [...formulario.querySelectorAll('[name="forma_pagamento"]')].every((o) => o.required),
        };
    }

    function mudar(campo, valor, evento = 'change') {
        campo.value = valor;
        campo.dispatchEvent(new Event(evento, { bubbles: true }));
    }

    test('no balcão é obrigatória', () => {
        const tela = montarFormulario();
        expect(tela.asteriscoVisivel()).toBe(true);
        expect(tela.opcoesObrigatorias()).toBe(true);
    });

    test('com cliente e sem pagamento na hora deixa de ser obrigatória', () => {
        const tela = montarFormulario();
        mudar(tela.cliente, '7');
        expect(tela.asteriscoVisivel()).toBe(false);
        expect(tela.opcoesObrigatorias()).toBe(false);
    });

    test('com cliente e valor pago agora volta a ser obrigatória', () => {
        const tela = montarFormulario();
        mudar(tela.cliente, '7');
        mudar(tela.pago, '10', 'input');
        expect(tela.asteriscoVisivel()).toBe(true);
    });

    test('na edição, venda com pagamento no ato continua obrigatória mesmo com cliente', () => {
        const tela = montarFormulario({ pagouNoAto: true });
        mudar(tela.cliente, '7');
        expect(formaDePagamentoObrigatoria(tela.formulario)).toBe(true);
        expect(tela.asteriscoVisivel()).toBe(true);
    });

    test('página sem a forma de pagamento não quebra', () => {
        document.body.innerHTML = '<form><select name="cliente"></select></form>';
        expect(() => iniciarFormaObrigatoria(document.querySelector('form'))).not.toThrow();
    });
});

describe('regras finas do carrinho (achadas pelo teste de mutação)', () => {
    beforeEach(() => { Element.prototype.scrollIntoView = jest.fn(); });

    test('ordem da busca: código igual, depois começa com (nome ou código), depois só contém', () => {
        const catalogo = [
            { id: 1, nome: 'Pão de queijo', codigo: 'X1' },
            { id: 2, nome: 'Queijo minas', codigo: 'Q2' },
            { id: 3, nome: 'Abacaxi', codigo: 'QUEIJO' },
            { id: 4, nome: 'Zeta', codigo: 'QUEIJO9' },
        ];
        expect(buscarProdutos(catalogo, 'queijo').map((p) => p.id)).toEqual([3, 2, 4, 1]);
    });

    test('subtotal da linha é preço × quantidade', () => {
        const { busca } = montarPagina();
        digitar(busca, 'p01');
        tecla(busca, 'Enter');
        document.querySelector('[aria-label="Aumentar Pão francês"]').click();
        document.querySelector('[aria-label="Aumentar Pão francês"]').click();
        expect(document.querySelector('.item-carrinho .w-24').textContent).toBe(formatarReais(2.4));
        expect(document.querySelector('[data-carrinho-vazio]').classList.contains('hidden')).toBe(true);
    });

    test('resultado mostra código e estoque; 1 unidade ainda vende, 0 é "sem estoque"', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'p01');
        expect(resultados.textContent).toContain('#P01 · 100 em estoque');
        digitar(busca, 'coado');
        expect(resultados.textContent).toContain('10 em estoque');
        expect(resultados.textContent).not.toContain('#');
        digitar(busca, 'bolo');
        expect(resultados.textContent).toContain('#B1 · sem estoque');
        expect(resultados.querySelector('[role=option]').getAttribute('aria-disabled')).toBe('true');
    });

    test('produto com 1 unidade não aparece como sem estoque', () => {
        document.body.innerHTML = `
            <div data-carrinho data-catalogo="ultimo">
                <input id="busca-produto"><ul id="resultados-produto" class="hidden"></ul>
                <ul data-itens-lista></ul><p data-carrinho-vazio></p><strong data-total></strong>
            </div>
            <script type="application/json" id="ultimo">[{"id": 9, "nome": "Último", "codigo": "", "preco": "1.00", "estoque": 1}]</script>`;
        iniciarCarrinho(document.querySelector('[data-carrinho]'));
        const busca = document.getElementById('busca-produto');
        digitar(busca, 'ultimo');
        const opcao = document.querySelector('[role=option]');
        expect(opcao.textContent).toContain('1 em estoque');
        expect(opcao.getAttribute('aria-disabled')).toBe('false');
    });

    test('clique em produto esgotado não adiciona; em produto com estoque adiciona', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'bolo');
        resultados.querySelector('[role=option]').dispatchEvent(new MouseEvent('mousedown', { cancelable: true }));
        expect(enviados().produtos).toEqual([]);
        digitar(busca, 'coado');
        resultados.querySelector('[role=option]').dispatchEvent(new MouseEvent('mousedown', { cancelable: true }));
        expect(enviados().produtos).toEqual(['3']);
    });

    test('Enter no produto esgotado não adiciona', () => {
        const { busca } = montarPagina();
        digitar(busca, 'bolo');
        tecla(busca, 'Enter');
        expect(enviados().produtos).toEqual([]);
    });

    test('setas andam uma posição e dão a volta; a opção ativa fica marcada', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'o'); // pão de queijo, pão francês, café coado, bolo...
        const marcadas = () => [...resultados.children].map((o) => o.getAttribute('aria-selected'));
        expect(marcadas()[0]).toBe('true');
        expect(marcadas().filter((m) => m === 'true')).toHaveLength(1);
        tecla(busca, 'ArrowDown');
        expect(marcadas()[1]).toBe('true');
        tecla(busca, 'ArrowUp');
        tecla(busca, 'ArrowUp');
        expect(marcadas()[marcadas().length - 1]).toBe('true');
        expect(busca.getAttribute('aria-activedescendant')).toBe(resultados.lastElementChild.id);
    });

    test('passar o mouse marca a opção; Escape fecha a lista e outras teclas não', () => {
        const { busca, resultados } = montarPagina();
        digitar(busca, 'o');
        resultados.children[2].dispatchEvent(new MouseEvent('mousemove'));
        expect(resultados.children[2].getAttribute('aria-selected')).toBe('true');
        tecla(busca, 'a');
        expect(resultados.classList.contains('hidden')).toBe(false);
        tecla(busca, 'Escape');
        expect(resultados.classList.contains('hidden')).toBe(true);
    });

    test('setas sem resultado não marcam nada', () => {
        const { busca } = montarPagina();
        digitar(busca, 'xyz');
        tecla(busca, 'ArrowDown');
        expect(busca.hasAttribute('aria-activedescendant')).toBe(false);
    });

    test('formulário com cliente mas sem o resumo não quebra', () => {
        document.body.innerHTML = '<form><select name="cliente"><option value="">Balcão</option></select></form>';
        expect(() => iniciarResumoDePagamento(document.querySelector('form'))).not.toThrow();
    });

    test('ao carregar a página, o carrinho dentro de um formulário liga também o resumo', () => {
        document.body.innerHTML = `
            <form>
                <select name="cliente"><option value="">Balcão</option></select>
                <div data-pago-agora><input name="valor_pago"></div><p data-resumo-pagamento></p>
                <div data-carrinho data-catalogo="catalogo">
                    <input id="busca-produto"><ul id="resultados-produto" class="hidden"></ul>
                    <ul data-itens-lista></ul><p data-carrinho-vazio></p><strong data-total></strong>
                </div>
            </form>
            <script type="application/json" id="catalogo">${JSON.stringify(CATALOGO)}</script>`;
        document.dispatchEvent(new Event('DOMContentLoaded'));
        expect(document.querySelector('[data-resumo-pagamento]').textContent).toBe('Venda de balcão: paga na hora.');
    });
});


describe('vencimento', () => {
    const HOJE = () => new Date(2026, 0, 28);

    function montar({ comPagoAgora = true, pagouNoAto } = {}) {
        document.body.innerHTML = `
            <form ${pagouNoAto ? `data-pagou-no-ato="${pagouNoAto}"` : ''}>
                <select name="cliente"><option value="">Balcão</option><option value="7">Ana</option></select>
                ${comPagoAgora ? '<input name="valor_pago">' : ''}
                <div data-vencimento>
                    <input type="date" name="vencimento">
                    <button type="button" data-prazo-dias="7"></button><button type="button" data-prazo-dias=""></button>
                </div>
            </form>`;
        const formulario = document.querySelector('form');
        iniciarVencimento(formulario, HOJE);
        const total = (valor) => formulario.dispatchEvent(new CustomEvent('carrinho:total', { detail: { total: valor } }));
        return {
            formulario, total,
            cliente: formulario.querySelector('[name="cliente"]'),
            pago: formulario.querySelector('[name="valor_pago"]'),
            data: formulario.querySelector('[name="vencimento"]'),
            visivel: () => !formulario.querySelector('[data-vencimento]').classList.contains('hidden'),
        };
    }

    function mudar(campo, valor, evento = 'change') {
        campo.value = valor;
        campo.dispatchEvent(new Event(evento, { bubbles: true }));
    }

    test('soma dias virando o mês e o ano, com dois dígitos', () => {
        expect(somarDias(new Date(2026, 0, 28), 7)).toBe('2026-02-04');
        expect(somarDias(new Date(2026, 11, 30), 3)).toBe('2027-01-02');
        expect(somarDias(new Date(2026, 8, 1), 0)).toBe('2026-09-01');
    });

    test('só aparece com cliente e quando sobra algo para a caderneta', () => {
        const tela = montar();
        tela.total(50);
        expect(tela.visivel()).toBe(false);

        mudar(tela.cliente, '7');
        expect(tela.visivel()).toBe(true);

        mudar(tela.pago, '50', 'input');
        expect(tela.visivel()).toBe(false);

        mudar(tela.pago, '49.99', 'input');
        expect(tela.visivel()).toBe(true);
    });

    test('carrinho vazio esconde', () => {
        const tela = montar();
        mudar(tela.cliente, '7');
        tela.total(0);
        expect(tela.visivel()).toBe(false);
    });

    test('na edição usa o que foi pago no ato', () => {
        const tela = montar({ comPagoAgora: false, pagouNoAto: '40.00' });
        mudar(tela.cliente, '7');
        tela.total(40);
        expect(tela.visivel()).toBe(false);
        tela.total(60);
        expect(tela.visivel()).toBe(true);
    });

    test('na edição sem pagamento no ato, todo o total fica a prazo', () => {
        const tela = montar({ comPagoAgora: false });
        mudar(tela.cliente, '7');
        tela.total(1);
        expect(tela.visivel()).toBe(true);
    });

    test('botões de prazo preenchem a data e "sem prazo" limpa', () => {
        const tela = montar();
        tela.formulario.querySelector('[data-prazo-dias="7"]').click();
        expect(tela.data.value).toBe('2026-02-04');
        tela.formulario.querySelector('[data-prazo-dias=""]').click();
        expect(tela.data.value).toBe('');
    });

    test('usa a data de hoje quando não recebe outra', () => {
        document.body.innerHTML = `<form><select name="cliente"></select>
            <div data-vencimento><input type="date" name="vencimento"><button data-prazo-dias="1"></button></div></form>`;
        iniciarVencimento(document.querySelector('form'));
        document.querySelector('[data-prazo-dias]').click();
        expect(document.querySelector('[name="vencimento"]').value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    test('página sem o campo não quebra', () => {
        document.body.innerHTML = '<form><select name="cliente"></select></form>';
        expect(() => iniciarVencimento(document.querySelector('form'))).not.toThrow();
        document.body.innerHTML = '<form><div data-vencimento></div></form>';
        expect(() => iniciarVencimento(document.querySelector('form'))).not.toThrow();
    });
});

describe('unidades e estoque sem controle', () => {
    const QUEIJO = { id: 1, nome: 'Queijo', codigo: 'Q', preco: '39.90', estoque: 2.35, unidade: 'kg', casas: 3 };
    const BOLO = { id: 3, nome: 'Bolo sob encomenda', codigo: '', preco: '50.00', estoque: null, unidade: 'un.', casas: 0 };

    test('subtotal em centavos arredonda como o servidor', () => {
        expect(subtotal({ preco: 39.9, quantidade: 0.35 })).toBe(13.97);
        expect(subtotal({ preco: 0.8, quantidade: 3 })).toBe(2.4);
        expect(totalDoCarrinho([{ preco: 39.9, quantidade: 0.35 }, { preco: 0.1, quantidade: 3 }])).toBeCloseTo(14.27);
    });

    test('textos de estoque e preço conforme a unidade', () => {
        expect(descreverEstoque(QUEIJO)).toBe('2,35 kg em estoque');
        expect(descreverEstoque(BOLO)).toBe('sem controle de estoque');
        expect(descreverEstoque({ estoque: 3 })).toBe('3 em estoque');
        expect(descreverPreco(QUEIJO, 39.9)).toBe(`${formatarReais(39.9)} por kg`);
        expect(descreverPreco(BOLO, 50)).toBe(`${formatarReais(50)} cada`);
    });

    test('por quilo aceita frações, com passo e limite do estoque', () => {
        const { carrinho } = montarPagina();
        carrinho.adicionar(QUEIJO);
        const campo = document.querySelector('.quantidade-campo');
        expect([campo.step, campo.min, campo.max, campo.inputMode]).toEqual(['0.001', '0.001', '2.35', 'decimal']);
        expect(campo.getAttribute('aria-label')).toBe('Quantidade de Queijo em kg');

        campo.value = '0.3456';
        campo.dispatchEvent(new Event('change'));
        expect(enviados().quantidades).toEqual(['0.346']);
        expect(total()).toBe(formatarReais(13.81));

        const campoNovo = document.querySelector('.quantidade-campo');
        campoNovo.value = '9';
        campoNovo.dispatchEvent(new Event('change'));
        expect(enviados().quantidades).toEqual(['2.35']);
    });

    test('pouco estoque fracionado entra com o que tem; o menos para no mínimo', () => {
        const { carrinho } = montarPagina();
        carrinho.adicionar({ ...QUEIJO, estoque: 0.5 });
        expect(enviados().quantidades).toEqual(['0.5']);
        document.querySelectorAll('.quantidade-botao')[0].click();
        expect(enviados().quantidades).toEqual(['0.001']);
        expect(document.querySelectorAll('.quantidade-botao')[0].disabled).toBe(true);
    });

    test('sem controle de estoque vende qualquer quantidade e aparece na busca', () => {
        const { carrinho, busca, resultados } = montarPagina();
        carrinho.adicionar(BOLO);
        const campo = document.querySelector('.quantidade-campo');
        expect(campo.hasAttribute('max')).toBe(false);
        expect(campo.inputMode).toBe('numeric');
        campo.value = '500';
        campo.dispatchEvent(new Event('change'));
        expect(enviados().quantidades).toEqual(['500']);
        expect(document.querySelectorAll('.quantidade-botao')[1].disabled).toBe(false);

        const pagina = montarPagina({ catalogo: [BOLO] });
        digitar(pagina.busca, 'bolo');
        expect(pagina.resultados.textContent).toContain('sem controle de estoque');
        tecla(pagina.busca, 'Enter');
        expect(enviados().produtos).toEqual(['3']);
    });
});

/**
 * @jest-environment jsdom
 */
const {
    normalizar, buscarProdutos, totalDoCarrinho, formatarReais, iniciarCarrinho, iniciarResumoDePagamento,
} = require('../js/venda.js');

const CATALOGO = [
    { id: 1, nome: 'Pão francês', codigo: 'P01', preco: '0.80', estoque: 100 },
    { id: 2, nome: 'Pão de queijo', codigo: 'PQ', preco: '3.50', estoque: 2 },
    { id: 3, nome: 'Café coado', codigo: '', preco: '5.00', estoque: 10 },
    { id: 4, nome: 'Bolo esgotado', codigo: 'B1', preco: '30.00', estoque: 0 },
];

function montarPagina({ itens = null, comResumo = false } = {}) {
    document.body.innerHTML = `
        <form>
            ${comResumo ? `<select name="cliente"><option value="">Balcão</option><option value="7">Ana</option></select>
            <div data-pago-agora><input name="valor_pago"></div><p data-resumo-pagamento></p>` : ''}
            <div data-carrinho data-catalogo="catalogo" ${itens ? 'data-itens="iniciais"' : ''}>
                <input id="busca-produto"><ul id="resultados-produto" class="hidden"></ul>
                <ul data-itens-lista></ul><p data-carrinho-vazio></p><strong data-total></strong>
            </div>
        </form>
        <script type="application/json" id="catalogo">${JSON.stringify(CATALOGO)}</script>
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
});

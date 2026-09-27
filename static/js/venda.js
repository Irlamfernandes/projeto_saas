/*
 * Carrinho da venda: busca de produtos (nome ou código, sem se importar com acentos) e lista de itens.
 * Marcação em interfaces/_carrinho.html. Envia listas paralelas item_produto[] e item_quantidade[].
 */

const LIMITE_DE_RESULTADOS = 8;
const reais = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

function formatarReais(valor) {
    return reais.format(valor);
}

function normalizar(texto) {
    return (texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/* Código igual primeiro, depois nomes que começam com o termo, depois o resto que contém. */
function buscarProdutos(catalogo, termo, limite = LIMITE_DE_RESULTADOS) {
    const busca = normalizar(termo);
    if (!busca) return [];
    const pontuar = (produto) => {
        const nome = normalizar(produto.nome);
        const codigo = normalizar(produto.codigo);
        if (codigo === busca) return 0;
        if (nome.startsWith(busca) || codigo.startsWith(busca)) return 1;
        if (nome.includes(busca) || codigo.includes(busca)) return 2;
        return null;
    };
    return catalogo
        .map((produto) => ({ produto, pontos: pontuar(produto) }))
        .filter(({ pontos }) => pontos !== null)
        .sort((a, b) => a.pontos - b.pontos || a.produto.nome.localeCompare(b.produto.nome, 'pt-BR'))
        .slice(0, limite)
        .map(({ produto }) => produto);
}

function totalDoCarrinho(itens) {
    return itens.reduce((soma, item) => soma + item.preco * item.quantidade, 0);
}

function criarElemento(tag, classes, texto) {
    const elemento = document.createElement(tag);
    if (classes) elemento.className = classes;
    if (texto !== undefined) elemento.textContent = texto;
    return elemento;
}

function botaoIcone(icone, rotulo, classes) {
    const botao = criarElemento('button', classes);
    botao.type = 'button';
    botao.setAttribute('aria-label', rotulo);
    botao.innerHTML = `<svg class="ico ico-sm"><use href="#${icone}"/></svg>`;
    return botao;
}

function lerJson(id) {
    const fonte = id && document.getElementById(id);
    return fonte ? JSON.parse(fonte.textContent) : [];
}

function iniciarCarrinho(raiz) {
    const catalogo = lerJson(raiz.dataset.catalogo);
    const porId = new Map(catalogo.map((produto) => [produto.id, produto]));
    const busca = raiz.querySelector('#busca-produto');
    const resultados = raiz.querySelector('#resultados-produto');
    const lista = raiz.querySelector('[data-itens-lista]');
    const vazio = raiz.querySelector('[data-carrinho-vazio]');
    const total = raiz.querySelector('[data-total]');
    const itens = [];
    let encontrados = [];
    let ativo = -1;

    lerJson(raiz.dataset.itens).forEach((inicial) => {
        const produto = porId.get(inicial.id);
        if (produto) itens.push({ produto, quantidade: inicial.quantidade, preco: Number(inicial.preco) });
    });

    function adicionar(produto) {
        const existente = itens.find((item) => item.produto.id === produto.id);
        if (existente) {
            existente.quantidade = Math.min(existente.quantidade + 1, produto.estoque);
        } else if (produto.estoque > 0) {
            itens.push({ produto, quantidade: 1, preco: Number(produto.preco) });
        }
        busca.value = '';
        fecharResultados();
        desenharItens();
        busca.focus();
    }

    function mudarQuantidade(item, quantidade) {
        item.quantidade = Math.max(1, Math.min(Number(quantidade) || 1, item.produto.estoque));
        desenharItens();
    }

    function remover(item) {
        itens.splice(itens.indexOf(item), 1);
        desenharItens();
    }

    function desenharItens() {
        lista.replaceChildren(...itens.map(linhaDoItem));
        vazio.classList.toggle('hidden', itens.length > 0);
        const soma = totalDoCarrinho(itens);
        total.textContent = formatarReais(soma);
        busca.setCustomValidity('');
        raiz.dispatchEvent(new CustomEvent('carrinho:total', { bubbles: true, detail: { total: soma } }));
    }

    function linhaDoItem(item) {
        const linha = criarElemento('li', 'item-carrinho');
        const info = criarElemento('div', 'min-w-0 flex-1 basis-40'); // estreito: o nome ocupa a linha e os controles descem
        info.append(
            criarElemento('span', 'block font-semibold leading-snug', item.produto.nome),
            criarElemento('span', 'block text-xs text-tinta-fraca tabular-nums',
                `${formatarReais(item.preco)} cada · ${item.produto.estoque} em estoque`),
        );

        const quantidade = criarElemento('div', 'quantidade');
        const menos = botaoIcone('i-menos', `Diminuir ${item.produto.nome}`, 'quantidade-botao');
        const campo = criarElemento('input', 'quantidade-campo');
        const mais = botaoIcone('i-mais', `Aumentar ${item.produto.nome}`, 'quantidade-botao');
        Object.assign(campo, { type: 'number', min: 1, max: item.produto.estoque, value: item.quantidade, name: 'item_quantidade', inputMode: 'numeric' });
        campo.setAttribute('aria-label', `Quantidade de ${item.produto.nome}`);
        menos.disabled = item.quantidade <= 1;
        mais.disabled = item.quantidade >= item.produto.estoque;
        menos.addEventListener('click', () => mudarQuantidade(item, item.quantidade - 1));
        mais.addEventListener('click', () => mudarQuantidade(item, item.quantidade + 1));
        campo.addEventListener('change', () => mudarQuantidade(item, campo.value));
        quantidade.append(menos, campo, mais);

        const produto = criarElemento('input');
        Object.assign(produto, { type: 'hidden', name: 'item_produto', value: item.produto.id });

        const subtotal = criarElemento('span', 'w-24 text-right font-semibold tabular-nums', formatarReais(item.preco * item.quantidade));
        const tirar = botaoIcone('i-lixeira', `Tirar ${item.produto.nome} da venda`, 'btn-fantasma btn-pequeno px-2 text-critico-texto');
        tirar.addEventListener('click', () => remover(item));

        const acoes = criarElemento('div', 'flex items-center gap-2');
        acoes.append(quantidade, subtotal, tirar);
        linha.append(info, acoes, produto);
        return linha;
    }

    function desenharResultados() {
        encontrados = buscarProdutos(catalogo, busca.value);
        ativo = encontrados.length ? 0 : -1;
        if (!busca.value.trim()) return fecharResultados();

        resultados.replaceChildren(...(encontrados.length
            ? encontrados.map(opcaoDoProduto)
            : [criarElemento('li', 'px-3 py-3 text-sm text-tinta-fraca', 'Nenhum produto com esse nome ou código.')]));
        resultados.classList.remove('hidden');
        busca.setAttribute('aria-expanded', 'true');
        marcarAtivo();
    }

    function opcaoDoProduto(produto, indice) {
        const opcao = criarElemento('li', 'opcao-busca');
        opcao.id = `produto-${produto.id}`;
        opcao.setAttribute('role', 'option');
        const semEstoque = produto.estoque < 1;
        opcao.setAttribute('aria-disabled', String(semEstoque));
        const nome = criarElemento('span', 'min-w-0');
        nome.append(
            criarElemento('span', 'block font-semibold truncate', produto.nome),
            criarElemento('span', 'block text-xs text-tinta-fraca',
                [produto.codigo && `#${produto.codigo}`, semEstoque ? 'sem estoque' : `${produto.estoque} em estoque`].filter(Boolean).join(' · ')),
        );
        opcao.append(nome, criarElemento('span', 'shrink-0 font-semibold tabular-nums', formatarReais(Number(produto.preco))));
        // mousedown (antes do blur do campo) para o clique não se perder ao fechar a lista.
        opcao.addEventListener('mousedown', (evento) => {
            evento.preventDefault();
            if (!semEstoque) adicionar(produto);
        });
        opcao.addEventListener('mousemove', () => { ativo = indice; marcarAtivo(); });
        return opcao;
    }

    function marcarAtivo() {
        Array.from(resultados.children).forEach((opcao, indice) => opcao.setAttribute('aria-selected', String(indice === ativo)));
        const opcao = resultados.children[ativo];
        if (opcao && opcao.id) {
            busca.setAttribute('aria-activedescendant', opcao.id);
            opcao.scrollIntoView?.({ block: 'nearest' });
        } else {
            busca.removeAttribute('aria-activedescendant');
        }
    }

    function fecharResultados() {
        resultados.classList.add('hidden');
        resultados.replaceChildren();
        busca.setAttribute('aria-expanded', 'false');
        busca.removeAttribute('aria-activedescendant');
    }

    busca.addEventListener('input', desenharResultados);
    busca.addEventListener('focus', () => busca.value && desenharResultados());
    busca.addEventListener('blur', fecharResultados);
    busca.addEventListener('keydown', (evento) => {
        if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
            evento.preventDefault();
            if (!encontrados.length) return;
            const passo = evento.key === 'ArrowDown' ? 1 : -1;
            ativo = (ativo + passo + encontrados.length) % encontrados.length;
            marcarAtivo();
        } else if (evento.key === 'Enter') {
            evento.preventDefault(); // Enter na busca adiciona o produto; nunca envia a venda pela metade.
            const produto = encontrados[ativo];
            if (produto && produto.estoque > 0) adicionar(produto);
        } else if (evento.key === 'Escape') {
            fecharResultados();
        }
    });

    raiz.closest('form')?.addEventListener('submit', (evento) => {
        if (itens.length) return;
        evento.preventDefault();
        busca.setCustomValidity('Adicione pelo menos um produto à venda.');
        busca.reportValidity();
    });

    desenharItens();
    return { itens, adicionar, remover, mudarQuantidade };
}

/* Resumo de pagamento da nova venda: balcão é pago na hora; com cliente, o que não pagar fica na caderneta. */
function iniciarResumoDePagamento(formulario) {
    const cliente = formulario.querySelector('[name="cliente"]');
    const pagoAgora = formulario.querySelector('[name="valor_pago"]');
    const blocoPagoAgora = formulario.querySelector('[data-pago-agora]');
    const resumo = formulario.querySelector('[data-resumo-pagamento]');
    if (!cliente || !resumo) return;
    let total = 0;

    function atualizar() {
        const comCliente = Boolean(cliente.value);
        blocoPagoAgora?.classList.toggle('hidden', !comCliente);
        if (!comCliente) {
            resumo.textContent = total ? `Venda de balcão: ${formatarReais(total)} pagos na hora.` : 'Venda de balcão: paga na hora.';
            return;
        }
        const pago = Number(pagoAgora?.value) || 0;
        const fica = total - pago;
        resumo.textContent = fica > 0
            ? `Vai para a caderneta: ${formatarReais(fica)}.`
            : (fica < 0 ? `Sobra ${formatarReais(-fica)} de crédito para o cliente.` : 'Pago por completo agora.');
    }

    formulario.addEventListener('carrinho:total', (evento) => { total = evento.detail.total; atualizar(); });
    cliente.addEventListener('change', atualizar);
    pagoAgora?.addEventListener('input', atualizar);
    atualizar();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-carrinho]').forEach((raiz) => {
        const formulario = raiz.closest('form');
        if (formulario) iniciarResumoDePagamento(formulario);
        iniciarCarrinho(raiz);
    });
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { normalizar, buscarProdutos, totalDoCarrinho, formatarReais, iniciarCarrinho, iniciarResumoDePagamento };
}

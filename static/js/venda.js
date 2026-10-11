/*
 * Carrinho da venda: busca de produtos (nome ou código, sem se importar com acentos) e lista de itens.
 * Marcação em interfaces/_carrinho.html. Envia listas paralelas item_produto[], item_quantidade[] e item_variacao[]
 * (id da variação escolhida; vazio se o produto não tem). Produto com variações entra numa linha nova a cada vez.
 */

const LIMITE_DE_RESULTADOS = 8;
const reais = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const quantidades = new Intl.NumberFormat('pt-BR'); // até 3 casas, o padrão do formato
const POR_UNIDADE = 'un.';

function formatarReais(valor) {
    return reais.format(valor);
}

/* Produto sem controle de estoque (estoque null) vende qualquer quantidade. */
function limiteDoEstoque(produto) {
    return produto.estoque ?? Infinity;
}

/* Menor quantidade aceita: 1 para unidade, 0,001 para quilo (3 casas), 0,01 para metro... */
function passoDaQuantidade(produto) {
    return 10 ** -(produto.casas || 0);
}

/* Unidade que vale mostrar ao lado do número: 'kg', 'L'... (por unidade não precisa). */
function unidadeVisivel(produto) {
    return produto.unidade && produto.unidade !== POR_UNIDADE ? produto.unidade : '';
}

function descreverEstoque(produto) {
    if (produto.estoque === null) return 'sem controle de estoque';
    const unidade = unidadeVisivel(produto);
    const sufixo = unidade ? ` ${unidade}` : '';
    return `${quantidades.format(produto.estoque)}${sufixo} em estoque`;
}

function descreverPreco(produto, preco) {
    const unidade = unidadeVisivel(produto);
    const medida = unidade ? `por ${unidade}` : 'cada';
    return `${formatarReais(preco)} ${medida}`;
}

function temVariacoes(produto) {
    return (produto.variacoes || []).length > 0;
}

/* Preço do produto mais o acréscimo da variação (Azul G + R$ 5,00), em centavos inteiros. */
function precoComVariacao(produto, variacao) {
    const centavos = Math.round(Number(produto.preco) * 100) + Math.round(Number(variacao?.acrescimo || 0) * 100);
    return centavos / 100;
}

/* Item que já estava na venda (edição) e segue com a mesma variação mantém o preço da época, como no servidor. */
function precoDoItem(item) {
    if (item.original && (item.variacao?.id ?? null) === item.original.variacao) return item.original.preco;
    return precoComVariacao(item.produto, item.variacao);
}

function rotuloDaVariacao(variacao, livre) {
    const acrescimo = Number(variacao.acrescimo) ? ` (+${formatarReais(Number(variacao.acrescimo))})` : '';
    return livre <= 0 ? `${variacao.nome}${acrescimo} · sem estoque` : `${variacao.nome}${acrescimo}`;
}

/* Quantidade × preço em centavos, com contas inteiras (0,35 kg × R$ 39,90 = R$ 13,97, como no servidor). */
function subtotal(item) {
    const centavos = Math.round(item.preco * 100) * Math.round(item.quantidade * 1000);
    return Math.round(centavos / 1000) / 100;
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
    return itens.reduce((soma, item) => soma + subtotal(item), 0);
}

function criarElemento(tag, classes, texto = '') {
    const elemento = document.createElement(tag);
    if (classes) elemento.className = classes;
    elemento.textContent = texto;
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
    return JSON.parse(document.getElementById(id)?.textContent ?? '[]');
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
    // A lista de sugestões só existe com este script (as opções também ganham o papel aqui).
    resultados.setAttribute('role', 'listbox');
    resultados.setAttribute('aria-label', 'Produtos encontrados');
    // Stryker disable next-line UnaryOperator: antes da 1ª busca não há opções: -1 e +1 apontam para fora da lista igual.
    let ativo = -1;

    lerJson(raiz.dataset.itens).forEach((inicial) => {
        const produto = porId.get(inicial.id);
        if (!produto) return;
        const variacao = (produto.variacoes || []).find((candidata) => candidata.id === inicial.variacao) || null;
        const original = { preco: Number(inicial.preco), variacao: inicial.variacao ?? null };
        itens.push({ produto, variacao, quantidade: inicial.quantidade, original, preco: original.preco });
    });

    /* O que ainda dá para vender (do produto ou da variação), descontando as outras linhas iguais do carrinho. */
    function livre(produto, variacao = null, fora = null) {
        const usado = itens.filter((item) => item.produto.id === produto.id && item.variacao === variacao && item !== fora)
            .reduce((soma, item) => soma + item.quantidade, 0);
        return Number((limiteDoEstoque(variacao || produto) - usado).toFixed(3));
    }

    function adicionar(produto) {
        // Com variações, cada vez é uma linha nova: pode ser outra cor, outro tamanho...
        const existente = !temVariacoes(produto) && itens.find((item) => item.produto.id === produto.id);
        const disponivel = livre(produto);
        if (existente) {
            existente.quantidade += Math.min(1, disponivel);
        } else if (disponivel > 0) {
            const quantidade = temVariacoes(produto) ? 1 : Math.min(1, disponivel);
            itens.push({ produto, variacao: null, quantidade, preco: precoComVariacao(produto, null) });
        }
        busca.value = '';
        fecharResultados();
        desenharItens();
        busca.focus();
    }

    function mudarQuantidade(item, quantidade) {
        const casas = item.produto.casas || 0;
        const pedida = Number(String(quantidade).replace(',', '.')) || 1;
        const limitada = Math.min(pedida, livre(item.produto, item.variacao, item));
        item.quantidade = Math.max(passoDaQuantidade(item.produto), Number(limitada.toFixed(casas)));
        desenharItens();
    }

    function escolher(item, id) {
        item.variacao = item.produto.variacoes.find((variacao) => String(variacao.id) === id) || null;
        item.preco = precoDoItem(item);
        const disponivel = item.variacao ? livre(item.produto, item.variacao, item) : Infinity;
        item.quantidade = Math.max(passoDaQuantidade(item.produto), Math.min(item.quantidade, disponivel));
        desenharItens();
        lista.children[itens.indexOf(item)].querySelector('[data-variacao-item]').focus();
    }

    /* Seletor da variação (obrigatório). A que acabou aparece, mas não dá para escolher. */
    function seletorDeVariacao(item) {
        const campo = criarElemento('select', 'entrada entrada-pequena mt-1.5');
        campo.dataset.variacaoItem = '';
        campo.required = true;
        campo.setAttribute('aria-label', `Variação de ${item.produto.nome}`);
        campo.append(new Option('Escolha a variação…', ''), ...item.produto.variacoes.map((variacao) => {
            const disponivel = livre(item.produto, variacao, item);
            const opcao = new Option(rotuloDaVariacao(variacao, disponivel), String(variacao.id));
            opcao.disabled = disponivel <= 0 && variacao !== item.variacao;
            return opcao;
        }));
        campo.value = item.variacao ? String(item.variacao.id) : '';
        campo.addEventListener('change', () => escolher(item, campo.value));
        return campo;
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
        const estoque = item.variacao ? { ...item.produto, estoque: item.variacao.estoque } : item.produto;
        info.append(
            criarElemento('span', 'block font-semibold leading-snug', item.produto.nome),
            criarElemento('span', 'block text-xs text-tinta-fraca tabular-nums',
                `${descreverPreco(item.produto, item.preco)} · ${descreverEstoque(estoque)}`),
        );
        if (temVariacoes(item.produto)) info.append(seletorDeVariacao(item));

        const quantidade = criarElemento('div', 'quantidade');
        const menos = botaoIcone('i-menos', `Diminuir ${item.produto.nome}`, 'quantidade-botao');
        const campo = criarElemento('input', 'quantidade-campo');
        const mais = botaoIcone('i-mais', `Aumentar ${item.produto.nome}`, 'quantidade-botao');
        const passo = passoDaQuantidade(item.produto);
        const limite = livre(item.produto, item.variacao, item); // sem variação escolhida: o total do produto
        Object.assign(campo, {
            type: 'number', min: passo, step: passo, value: item.quantidade, name: 'item_quantidade',
            inputMode: passo < 1 ? 'decimal' : 'numeric',
        });
        if (limite !== Infinity) campo.max = limite;
        const unidade = unidadeVisivel(item.produto);
        const emUnidade = unidade ? ` em ${unidade}` : '';
        campo.setAttribute('aria-label', `Quantidade de ${item.produto.nome}${emUnidade}`);
        menos.disabled = item.quantidade <= passo;
        mais.disabled = item.quantidade >= limite;
        menos.addEventListener('click', () => mudarQuantidade(item, item.quantidade - 1));
        mais.addEventListener('click', () => mudarQuantidade(item, item.quantidade + 1));
        campo.addEventListener('change', () => mudarQuantidade(item, campo.value));
        quantidade.append(menos, campo, mais);

        const produto = criarElemento('input');
        Object.assign(produto, { type: 'hidden', name: 'item_produto', value: item.produto.id });
        const variacao = criarElemento('input');
        Object.assign(variacao, { type: 'hidden', name: 'item_variacao', value: item.variacao ? item.variacao.id : '' });

        const valor = criarElemento('span', 'w-24 text-right font-semibold tabular-nums', formatarReais(subtotal(item)));
        const tirar = botaoIcone('i-lixeira', `Tirar ${item.produto.nome} da venda`, 'btn-fantasma btn-pequeno px-2 text-critico-texto');
        tirar.addEventListener('click', () => remover(item));

        // Em telas bem estreitas (menos de ~340px) a lixeira desce para a linha de baixo, em vez de alargar a página.
        const acoes = criarElemento('div', 'flex flex-wrap items-center justify-end gap-2');
        acoes.append(quantidade, valor, tirar);
        linha.append(info, acoes, produto, variacao);
        return linha;
    }

    function desenharResultados() {
        encontrados = buscarProdutos(catalogo, busca.value);
        // Stryker disable next-line UnaryOperator: sem resultados, -1 e +1 apontam para fora da lista do mesmo jeito.
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
        const semEstoque = limiteDoEstoque(produto) <= 0;
        opcao.setAttribute('aria-disabled', String(semEstoque));
        const nome = criarElemento('span', 'min-w-0');
        nome.append(
            criarElemento('span', 'block font-semibold truncate', produto.nome),
            criarElemento('span', 'block text-xs text-tinta-fraca',
                [produto.codigo && `#${produto.codigo}`, semEstoque ? 'sem estoque' : descreverEstoque(produto)].filter(Boolean).join(' · ')),
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
        if (opcao?.id) {
            busca.setAttribute('aria-activedescendant', opcao.id);
            opcao.scrollIntoView({ block: 'nearest' });
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
            // Stryker disable next-line ConditionalExpression: sem resultados a conta daria NaN, que também não marca nenhuma opção; fica pela clareza.
            if (!encontrados.length) return;
            const passo = evento.key === 'ArrowDown' ? 1 : -1;
            ativo = (ativo + passo + encontrados.length) % encontrados.length;
            marcarAtivo();
        } else if (evento.key === 'Enter') {
            evento.preventDefault(); // Enter na busca adiciona o produto; nunca envia a venda pela metade.
            const produto = encontrados[ativo];
            if (produto && limiteDoEstoque(produto) > 0) adicionar(produto);
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

/* Frase do resumo quando a venda tem cliente: `fica` é o que falta pagar (negativo vira crédito). */
function resumoComCliente(fica) {
    if (fica > 0) return `Vai para a caderneta: ${formatarReais(fica)}.`;
    if (fica < 0) return `Sobra ${formatarReais(-fica)} de crédito para o cliente.`;
    return 'Pago por completo agora.';
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
        resumo.textContent = resumoComCliente(total - pago);
    }

    formulario.addEventListener('carrinho:total', (evento) => { total = evento.detail.total; atualizar(); });
    cliente.addEventListener('change', atualizar);
    pagoAgora?.addEventListener('input', atualizar);
    atualizar();
}

/* Data `dias` depois de `data`, no formato do campo de data (aaaa-mm-dd, no fuso de quem usa). */
function somarDias(data, dias) {
    const alvo = new Date(data.getFullYear(), data.getMonth(), data.getDate() + dias);
    const doisDigitos = (numero) => String(numero).padStart(2, '0');
    return `${alvo.getFullYear()}-${doisDigitos(alvo.getMonth() + 1)}-${doisDigitos(alvo.getDate())}`;
}

/* Valor de cada parcela como o servidor divide: partes iguais em centavos, o que sobrar vai na última. */
function dividirEmParcelas(valor, partes) {
    const centavos = Math.round(valor * 100);
    const parte = Math.floor(centavos / partes);
    return [...new Array(partes - 1).fill(parte), centavos - parte * (partes - 1)].map((c) => c / 100);
}

/* Datas das parcelas: a primeira e as seguintes a cada `intervalo` dias (texto aaaa-mm-dd). */
function datasDasParcelas(primeira, quantidade, intervalo) {
    const [ano, mes, dia] = primeira.split('-').map(Number);
    return Array.from({ length: quantidade }, (_, indice) => somarDias(new Date(ano, mes - 1, dia), indice * intervalo));
}

function resumoDasParcelas(valor, quantidade) {
    const valores = dividirEmParcelas(valor, quantidade);
    const ultima = valores.at(-1);
    const diferenca = ultima === valores[0] ? '' : ` (a última de ${formatarReais(ultima)})`;
    return `${quantidade} parcelas de ${formatarReais(valores[0])}${diferenca}`;
}

/* Campo de data da parcela `indice + 1` (a 1ª é o campo principal do "Vence em"). */
function campoDaParcela(indice, valor) {
    const linha = criarElemento('li', 'flex items-center gap-3');
    const campo = criarElemento('input', 'entrada tabular-nums');
    Object.assign(campo, { type: 'date', name: 'vencimento', value: valor, id: `vencimento-parcela-${indice + 1}` });
    const rotulo = criarElemento('label', 'w-24 shrink-0 text-sm font-semibold text-tinta-suave', `${indice + 1}ª parcela`);
    rotulo.htmlFor = campo.id;
    linha.append(rotulo, campo);
    return linha;
}

/* "Vence em" só aparece quando fica algo na caderneta: venda com cliente que não foi paga por completo no ato.
   Na edição, o que foi pago no ato vem em data-pagou-no-ato e as datas atuais em data-vencimentos.
   Com data escolhida, dá para parcelar: as datas seguintes são sugeridas pelo intervalo e podem ser ajustadas. */
function iniciarVencimento(formulario, hoje = () => new Date()) {
    const bloco = formulario.querySelector('[data-vencimento]');
    const cliente = formulario.querySelector('[name="cliente"]');
    if (!bloco || !cliente) return;
    const data = bloco.querySelector('[name="vencimento"]');
    const pagoAgora = formulario.querySelector('[name="valor_pago"]');
    const opcoes = bloco.querySelector('[data-opcoes-parcelas]');
    const numero = bloco.querySelector('[data-numero-parcelas]');
    const intervalo = bloco.querySelector('[data-intervalo-parcelas]');
    const lista = bloco.querySelector('[data-parcelas]');
    const resumo = bloco.querySelector('[data-resumo-parcelas]');
    let total = 0;

    const aPrazo = () => total - (Number(pagoAgora ? pagoAgora.value : formulario.dataset.pagouNoAto) || 0);

    /* Refaz os campos das parcelas 2 em diante (a 1ª é o campo principal). */
    function desenharParcelas(seguintes) {
        lista.replaceChildren(...seguintes.map((valor, indice) => campoDaParcela(indice + 1, valor)));
        atualizarResumo();
    }

    function sugerirDatas() {
        desenharParcelas(data.value ? datasDasParcelas(data.value, Number(numero.value), Number(intervalo.value)).slice(1) : []);
    }

    function atualizarResumo() {
        const quantidade = lista.children.length + 1;
        resumo.textContent = quantidade > 1 && aPrazo() > 0 ? resumoDasParcelas(aPrazo(), quantidade) : '';
    }

    function atualizar() {
        bloco.classList.toggle('hidden', !cliente.value || aPrazo() <= 0);
        opcoes.classList.toggle('hidden', !data.value);
        atualizarResumo();
    }

    bloco.querySelectorAll('[data-prazo-dias]').forEach((botao) => {
        botao.addEventListener('click', () => {
            // Stryker disable next-line StringLiteral: o campo de data descarta texto que não é data, então qualquer texto vira ''.
            data.value = botao.dataset.prazoDias ? somarDias(hoje(), Number(botao.dataset.prazoDias)) : '';
            if (!data.value) numero.value = '1';
            sugerirDatas();
            atualizar();
        });
    });
    data.addEventListener('change', () => { sugerirDatas(); atualizar(); });
    numero.addEventListener('change', sugerirDatas);
    intervalo.addEventListener('change', sugerirDatas);
    formulario.addEventListener('carrinho:total', (evento) => { total = evento.detail.total; atualizar(); });
    cliente.addEventListener('change', atualizar);
    pagoAgora?.addEventListener('input', atualizar);

    // Na edição, começa com as parcelas que a venda já tem.
    // Stryker disable next-line StringLiteral: sem o atributo, qualquer texto vira uma data só, e uma data só não parcela.
    const atuais = (bloco.dataset.vencimentos || '').split(' ').filter(Boolean); // o template deixa um espaço no fim
    // Stryker disable next-line ConditionalExpression,EqualityOperator: com uma data só, o número já é 1 e não há parcelas a desenhar.
    if (atuais.length > 1) {
        numero.value = String(atuais.length);
        desenharParcelas(atuais.slice(1));
    }
    atualizar();
}

/* Mesma regra do servidor: a forma de pagamento é obrigatória no balcão ou quando houve pagamento no ato. */
function formaDePagamentoObrigatoria(formulario) {
    const cliente = formulario.querySelector('[name="cliente"]');
    const pagoAgora = formulario.querySelector('[name="valor_pago"]');
    return !cliente.value || 'pagouNoAto' in formulario.dataset || Number(pagoAgora?.value) > 0;
}

/* Mostra o * e liga o required da forma de pagamento só quando ela é obrigatória. */
function iniciarFormaObrigatoria(formulario) {
    const marca = formulario.querySelector('[data-forma-pagamento] .obrigatorio');
    const opcoes = formulario.querySelectorAll('[name="forma_pagamento"]');
    if (!marca || !formulario.querySelector('[name="cliente"]')) return;

    function atualizar() {
        const obrigatoria = formaDePagamentoObrigatoria(formulario);
        marca.classList.toggle('hidden', !obrigatoria);
        opcoes.forEach((opcao) => { opcao.required = obrigatoria; });
    }

    formulario.addEventListener('change', atualizar);
    formulario.addEventListener('input', atualizar);
    atualizar();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-carrinho]').forEach((raiz) => {
        const formulario = raiz.closest('form');
        if (formulario) {
            iniciarResumoDePagamento(formulario);
            iniciarFormaObrigatoria(formulario);
            iniciarVencimento(formulario);
        }
        iniciarCarrinho(raiz);
    });
});

/* istanbul ignore else */
// Stryker disable next-line all: no Jest `module` sempre existe; a linha só serve para os testes importarem o arquivo.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        normalizar, buscarProdutos, totalDoCarrinho, precoComVariacao, precoDoItem, rotuloDaVariacao, formatarReais, subtotal, descreverEstoque, descreverPreco, iniciarCarrinho, iniciarResumoDePagamento,
        formaDePagamentoObrigatoria, iniciarFormaObrigatoria, somarDias, iniciarVencimento, dividirEmParcelas,
        datasDasParcelas, resumoDasParcelas,
    };
}

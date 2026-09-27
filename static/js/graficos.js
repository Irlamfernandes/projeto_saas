/*
 * Gráficos da aplicação (Chart.js).
 *
 * Cada gráfico é um <canvas data-grafico="TIPO" data-dados="ID" data-formato="moeda|unidades">,
 * onde ID aponta para um <script type="application/json"> gerado com |json_script:
 *   { rotulos: [...], detalhes: [...opcional, títulos do tooltip], series: [{ nome, valores, cor }] }
 * TIPO: linha | barras | barras-horizontais | barras-agrupadas
 * As cores vêm das variáveis CSS --cor-* (mesmos tokens do Tailwind).
 */

const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

function formatarMoeda(valor) {
    return moeda.format(valor);
}

function formatarMoedaCurta(valor) {
    if (Math.abs(valor) >= 1000) {
        return 'R$ ' + (valor / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' mil';
    }
    return 'R$ ' + Math.round(valor).toLocaleString('pt-BR');
}

function formatarUnidades(valor) {
    return valor.toLocaleString('pt-BR') + ' un.';
}

const FORMATOS = {
    moeda: { completo: formatarMoeda, eixo: formatarMoedaCurta },
    unidades: { completo: formatarUnidades, eixo: (v) => v.toLocaleString('pt-BR') },
};

/* O canvas só entende px: converte rem para px usando a letra da página (acompanha a letra grande do usuário). */
function remEmPx(rem) {
    const base = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    return rem * base;
}

function lerTokens(elemento) {
    const estilo = getComputedStyle(elemento || document.documentElement);
    const ler = (nome) => estilo.getPropertyValue(nome).trim();
    return {
        fonte: remEmPx(0.75),
        marca: ler('--cor-marca'),
        destaque: ler('--cor-destaque'),
        neutra: ler('--cor-neutra'),
        tinta: ler('--cor-tinta'),
        tintaSuave: ler('--cor-tinta-suave'),
        tintaFraca: ler('--cor-tinta-fraca'),
        linha: ler('--cor-linha'),
        grade: ler('--cor-grade'),
        superficie: ler('--cor-superficie'),
    };
}

function tooltip(tokens, formato, dados, mostrarSerie) {
    return {
        backgroundColor: tokens.tinta,
        // Balão no contraste do tema: escuro no claro, claro no escuro
        titleColor: tokens.superficie,
        bodyColor: tokens.superficie,
        padding: 10,
        cornerRadius: 10,
        displayColors: mostrarSerie,
        callbacks: {
            title: (itens) => (dados.detalhes ? dados.detalhes[itens[0].dataIndex] : itens[0].label),
            label: (item) => {
                const valor = formato.completo(item.parsed.y ?? item.parsed.x);
                return mostrarSerie ? `${item.dataset.label}: ${valor}` : valor;
            },
        },
    };
}

function eixoCategorias(tokens) {
    return {
        grid: { display: false },
        border: { color: tokens.linha },
        ticks: { color: tokens.tintaFraca, maxRotation: 0, autoSkipPadding: 14 },
    };
}

function eixoValores(tokens, formato) {
    return {
        beginAtZero: true,
        grid: { color: tokens.grade },
        border: { display: false },
        ticks: { color: tokens.tintaFraca, maxTicksLimit: 5, callback: formato.eixo },
    };
}

function montarLinha(dados, tokens, formato) {
    const [serie] = dados.series;
    const ultimo = serie.valores.length - 1;
    return {
        type: 'line',
        data: {
            labels: dados.rotulos,
            datasets: [{
                label: serie.nome,
                data: serie.valores,
                borderColor: tokens.marca,
                backgroundColor: tokens.marca + '1f',
                fill: true,
                borderWidth: 2,
                tension: 0.3,
                pointRadius: serie.valores.map((_, i) => (i === ultimo ? 4 : 0)),
                pointHoverRadius: 5,
                pointBackgroundColor: tokens.marca,
                pointBorderColor: tokens.superficie,
                pointBorderWidth: 2,
            }],
        },
        options: {
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: false }, tooltip: tooltip(tokens, formato, dados, false) },
            scales: { x: eixoCategorias(tokens), y: eixoValores(tokens, formato) },
        },
        plugins: [pluginMira(tokens)],
    };
}

function montarBarras(dados, tokens, formato) {
    return {
        type: 'bar',
        data: {
            labels: dados.rotulos,
            datasets: dados.series.map((serie) => ({
                label: serie.nome,
                data: serie.valores,
                backgroundColor: tokens[serie.cor] || tokens.marca,
                borderRadius: 4,
                borderSkipped: 'start',
                maxBarThickness: 36,
            })),
        },
        options: {
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            datasets: { bar: { categoryPercentage: 0.72, barPercentage: 0.92 } },
            plugins: { legend: { display: false }, tooltip: tooltip(tokens, formato, dados, dados.series.length > 1) },
            scales: { x: eixoCategorias(tokens), y: eixoValores(tokens, formato) },
        },
    };
}

function montarBarrasHorizontais(dados, tokens, formato) {
    const config = montarBarras(dados, tokens, formato);
    config.options.indexAxis = 'y';
    config.options.interaction = { mode: 'nearest', axis: 'y', intersect: false };
    config.options.layout = { padding: { right: 56 } };
    config.options.scales = {
        x: { display: false, beginAtZero: true },
        y: { grid: { display: false }, border: { display: false }, ticks: { color: tokens.tintaSuave } },
    };
    config.plugins = [pluginRotulosNoFim(tokens, formato)];
    return config;
}

const MONTADORES = {
    linha: montarLinha,
    barras: montarBarras,
    'barras-agrupadas': montarBarras,
    'barras-horizontais': montarBarrasHorizontais,
};

function montarConfiguracao(tipo, dados, tokens, nomeFormato) {
    const montador = MONTADORES[tipo];
    if (!montador) {
        throw new Error(`Tipo de gráfico desconhecido: ${tipo}`);
    }
    return montador(dados, tokens, FORMATOS[nomeFormato] || FORMATOS.moeda);
}

/* Linha vertical tracejada acompanhando o tooltip (gráfico de linha). */
function pluginMira(tokens) {
    return {
        id: 'mira',
        afterDatasetsDraw(grafico) {
            const ativos = grafico.tooltip?.getActiveElements?.() || [];
            if (!ativos.length) return;
            const { ctx, chartArea } = grafico;
            ctx.save();
            ctx.strokeStyle = tokens.tintaFraca;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(ativos[0].element.x, chartArea.top);
            ctx.lineTo(ativos[0].element.x, chartArea.bottom);
            ctx.stroke();
            ctx.restore();
        },
    };
}

/* Valor escrito no fim de cada barra horizontal (rótulo direto, dispensa o eixo). */
function pluginRotulosNoFim(tokens, formato) {
    return {
        id: 'rotulosNoFim',
        afterDatasetsDraw(grafico) {
            const { ctx } = grafico;
            const valores = grafico.data.datasets[0].data;
            ctx.save();
            ctx.fillStyle = tokens.tintaSuave;
            ctx.font = `600 ${tokens.fonte}px Figtree, system-ui, sans-serif`;
            ctx.textBaseline = 'middle';
            grafico.getDatasetMeta(0).data.forEach((barra, i) => {
                ctx.fillText(formato.eixo(valores[i]), barra.x + 6, barra.y);
            });
            ctx.restore();
        },
    };
}

function desenharGraficos(raiz = document, ChartClasse = globalThis.Chart) {
    if (!ChartClasse) return [];
    const tokens = lerTokens();
    ChartClasse.defaults.font.family = 'Figtree, system-ui, sans-serif';
    ChartClasse.defaults.font.size = tokens.fonte;
    if (globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
        ChartClasse.defaults.animation = false;
    }
    return Array.from(raiz.querySelectorAll('canvas[data-grafico]')).map((canvas) => {
        const fonte = document.getElementById(canvas.dataset.dados);
        const dados = JSON.parse(fonte.textContent);
        return new ChartClasse(canvas, montarConfiguracao(canvas.dataset.grafico, dados, tokens, canvas.dataset.formato));
    });
}

/* No tema "Automático", o aparelho pode trocar de claro para escuro com a tela aberta: redesenha com as cores novas. */
function acompanharTemaDoAparelho(graficos, redesenhar = desenharGraficos) {
    const escuro = globalThis.matchMedia?.('(prefers-color-scheme: dark)');
    if (!escuro?.addEventListener) return;
    let atuais = graficos;
    escuro.addEventListener('change', () => {
        atuais.forEach((grafico) => grafico.destroy());
        atuais = redesenhar();
    });
}

document.addEventListener('DOMContentLoaded', () => acompanharTemaDoAparelho(desenharGraficos()));

/* istanbul ignore else */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatarMoeda, formatarMoedaCurta, formatarUnidades, remEmPx, lerTokens, montarConfiguracao, desenharGraficos,
        acompanharTemaDoAparelho,
        pluginMira, pluginRotulosNoFim,
    };
}

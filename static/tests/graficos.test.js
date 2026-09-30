/**
 * @jest-environment jsdom
 */
const g = require('../js/graficos.js');

const tokens = {
    fonte: 12,
    marca: '#0d9488', destaque: '#c96a05', neutra: '#c9d3d1', tinta: '#16211f', tintaSuave: '#4b5b58',
    tintaFraca: '#7c8a87', linha: '#e2e9e7', grade: '#edf1f0', superficie: '#ffffff',
};
const dados = { rotulos: ['18/03', '19/03', '20/03'], detalhes: ['quarta', 'quinta', 'sexta'], series: [{ nome: 'Faturamento', valores: [10, 0, 1500.5], cor: 'marca' }] };
const semEspacoDuro = (t) => t.replace(/\u00a0/g, ' ');

function contextoFalso() {
    return {
        save: jest.fn(), restore: jest.fn(), beginPath: jest.fn(), moveTo: jest.fn(), lineTo: jest.fn(),
        stroke: jest.fn(), setLineDash: jest.fn(), fillText: jest.fn(),
    };
}

describe('formatação', () => {
    test('moeda, moeda curta e unidades em pt-BR', () => {
        expect(semEspacoDuro(g.formatarMoeda(1234.5))).toBe('R$ 1.234,50');
        expect(g.formatarMoedaCurta(1500)).toBe('R$ 1,5 mil');
        expect(g.formatarMoedaCurta(1234)).toBe('R$ 1,2 mil'); // uma casa depois da vírgula
        expect(g.formatarMoedaCurta(-2500)).toBe('R$ -2,5 mil');
        expect(g.formatarMoedaCurta(999.6)).toBe('R$ 1.000');
        expect(g.formatarUnidades(1200)).toBe('1.200 un.');
    });
});

describe('montarConfiguracao', () => {
    test('linha: uma série, destaque no último ponto, mira e tooltip com a data completa', () => {
        const config = g.montarConfiguracao('linha', dados, tokens, 'moeda');

        expect(config.type).toBe('line');
        expect(config.data.datasets[0].pointRadius).toEqual([0, 0, 4]);
        expect(config.data.datasets[0].borderColor).toBe('#0d9488');
        expect(config.plugins[0].id).toBe('mira');
        const tip = config.options.plugins.tooltip;
        expect(tip.displayColors).toBe(false);
        expect(tip.callbacks.title([{ dataIndex: 2, label: '20/03' }])).toBe('sexta');
        expect(semEspacoDuro(tip.callbacks.label({ parsed: { y: 1500.5 }, dataset: { label: 'Faturamento' } }))).toBe('R$ 1.500,50');
        expect(config.options.scales.y.ticks.callback(1500)).toBe('R$ 1,5 mil');
    });

    test('barras agrupadas: cor por série e nome da série no tooltip', () => {
        const agrupados = { rotulos: ['jan', 'fev'], series: [
            { nome: 'Vendido', valores: [100, 200], cor: 'marca' },
            { nome: 'Recebido', valores: [80, 150], cor: 'destaque' },
        ] };
        const config = g.montarConfiguracao('barras-agrupadas', agrupados, tokens, 'moeda');

        expect(config.data.datasets.map((d) => d.backgroundColor)).toEqual(['#0d9488', '#c96a05']);
        const tip = config.options.plugins.tooltip;
        expect(tip.displayColors).toBe(true);
        expect(tip.callbacks.title([{ dataIndex: 0, label: 'jan' }])).toBe('jan');
        expect(semEspacoDuro(tip.callbacks.label({ parsed: { y: 80 }, dataset: { label: 'Recebido' } }))).toBe('Recebido: R$ 80,00');
    });

    test('cor desconhecida cai na cor da marca', () => {
        const config = g.montarConfiguracao('barras', { rotulos: ['a'], series: [{ nome: 'x', valores: [1], cor: 'inexistente' }] }, tokens, 'moeda');
        expect(config.data.datasets[0].backgroundColor).toBe('#0d9488');
    });

    test('barras horizontais: eixo y, sem eixo x, rótulos no fim e formato de unidades', () => {
        const ranking = { rotulos: ['Pão', 'Bolo'], series: [{ nome: 'Unidades', valores: [412, 1200], cor: 'marca' }] };
        const config = g.montarConfiguracao('barras-horizontais', ranking, tokens, 'unidades');

        expect(config.options.indexAxis).toBe('y');
        expect(config.options.scales.x.display).toBe(false);
        expect(config.plugins[0].id).toBe('rotulosNoFim');
        expect(config.options.plugins.tooltip.callbacks.label({ parsed: { x: 412 }, dataset: { label: 'Unidades' } })).toBe('412 un.');

        const ctx = contextoFalso();
        config.plugins[0].afterDatasetsDraw({ ctx, data: config.data, getDatasetMeta: () => ({ data: [{ x: 1, y: 1 }, { x: 2, y: 2 }] }) });
        expect(ctx.fillText).toHaveBeenCalledWith('1.200', 8, 2);
    });

    test('formato desconhecido usa moeda; tipo desconhecido é erro', () => {
        const config = g.montarConfiguracao('barras', dados, tokens, undefined);
        expect(config.options.scales.y.ticks.callback(2000)).toBe('R$ 2 mil');
        expect(() => g.montarConfiguracao('pizza', dados, tokens, 'moeda')).toThrow('Tipo de gráfico desconhecido: pizza');
    });
});

describe('plugins', () => {
    test('mira desenha a linha só quando há tooltip ativo', () => {
        const ctx = contextoFalso();
        const grafico = { ctx, chartArea: { top: 10, bottom: 200 }, tooltip: { getActiveElements: () => [] } };
        const mira = g.pluginMira(tokens);

        mira.afterDatasetsDraw(grafico);
        expect(ctx.stroke).not.toHaveBeenCalled();

        grafico.tooltip.getActiveElements = () => [{ element: { x: 50 } }];
        mira.afterDatasetsDraw(grafico);
        expect(ctx.moveTo).toHaveBeenCalledWith(50, 10);
        expect(ctx.lineTo).toHaveBeenCalledWith(50, 200);
        expect(ctx.setLineDash).toHaveBeenCalledWith([3, 3]); // tracejada, para não parecer dado

        mira.afterDatasetsDraw({ ctx, chartArea: {} }); // sem tooltip
        expect(ctx.stroke).toHaveBeenCalledTimes(1);
    });

    test('rótulos no fim escrevem o valor ao lado de cada barra', () => {
        const ctx = contextoFalso();
        const grafico = {
            ctx,
            data: { datasets: [{ data: [412, 97] }] },
            getDatasetMeta: () => ({ data: [{ x: 100, y: 20 }, { x: 30, y: 50 }] }),
        };
        g.pluginRotulosNoFim(tokens, { eixo: (v) => `${v}` }).afterDatasetsDraw(grafico);

        expect(ctx.fillText).toHaveBeenCalledWith('412', 106, 20);
        expect(ctx.font).toBe('600 12px Figtree, system-ui, sans-serif');
        expect(ctx.fillText).toHaveBeenCalledWith('97', 36, 50);
    });
});

describe('desenharGraficos', () => {
    beforeEach(() => {
        document.documentElement.style.setProperty('--cor-marca', '#0d9488');
        document.body.innerHTML = `
            <script type="application/json" id="dados-faturamento">${JSON.stringify(dados)}</script>
            <canvas data-grafico="linha" data-dados="dados-faturamento" data-formato="moeda"></canvas>
            <canvas></canvas>`;
    });

    test('cria um Chart por canvas marcado, com a configuração montada', () => {
        const ChartFalso = jest.fn(function (canvas, config) { this.canvas = canvas; this.config = config; });
        ChartFalso.defaults = { font: {} };

        const graficos = g.desenharGraficos(document, ChartFalso);

        expect(graficos).toHaveLength(1);
        expect(ChartFalso.mock.calls[0][1].type).toBe('line');
        expect(ChartFalso.defaults.font.family).toContain('Figtree');
    });

    test('respeita a preferência por menos movimento', () => {
        window.matchMedia = jest.fn(() => ({ matches: true }));
        const ChartFalso = jest.fn();
        ChartFalso.defaults = { font: {} };

        g.desenharGraficos(document, ChartFalso);

        expect(ChartFalso.defaults.animation).toBe(false);
        delete window.matchMedia;
    });

    test('sem Chart.js carregado não faz nada', () => {
        expect(g.desenharGraficos(document, undefined)).toEqual([]);
    });

    test('desenha sozinho quando a página termina de carregar', () => {
        const ChartFalso = jest.fn();
        ChartFalso.defaults = { font: {} };
        globalThis.Chart = ChartFalso;

        document.dispatchEvent(new Event('DOMContentLoaded'));

        expect(ChartFalso).toHaveBeenCalledTimes(1);
        delete globalThis.Chart;
    });

    test('com o tema automático, redesenha quando o aparelho troca de claro para escuro', () => {
        let aoTrocar;
        window.matchMedia = jest.fn(() => ({ matches: false, addEventListener: (_evento, funcao) => { aoTrocar = funcao; } }));
        const antigo = { destroy: jest.fn() };
        const novo = { destroy: jest.fn() };
        const redesenhar = jest.fn(() => [novo]);

        g.acompanharTemaDoAparelho([antigo], redesenhar);
        aoTrocar();
        aoTrocar();

        expect(antigo.destroy).toHaveBeenCalledTimes(1);
        expect(novo.destroy).toHaveBeenCalledTimes(1);
        expect(redesenhar).toHaveBeenCalledTimes(2);
        delete window.matchMedia;
    });

    test('navegador sem aviso de troca de tema: não acompanha', () => {
        expect(() => g.acompanharTemaDoAparelho([])).not.toThrow();
        window.matchMedia = jest.fn(() => ({ matches: false }));
        expect(() => g.acompanharTemaDoAparelho([])).not.toThrow();
        delete window.matchMedia;
    });

    test('lerTokens lê as variáveis CSS, sem os espaços em volta', () => {
        expect(g.lerTokens().marca).toBe('#0d9488');
        const elemento = document.createElement('div');
        elemento.style.setProperty('--cor-marca', '  #123456  ');
        document.body.append(elemento);
        expect(g.lerTokens(elemento).marca).toBe('#123456');
    });

    test('texto dos gráficos acompanha a letra da página (rem)', () => {
        const ChartFalso = jest.fn();
        ChartFalso.defaults = { font: {} };

        document.documentElement.style.fontSize = '20px'; // usuário com letra grande
        g.desenharGraficos(document, ChartFalso);
        expect(g.remEmPx(0.75)).toBe(15);
        expect(ChartFalso.defaults.font.size).toBe(15);

        document.documentElement.style.fontSize = '';
        expect(g.remEmPx(0.75)).toBe(12); // padrão de 16px sem letra configurada
    });
});

describe('regras finas dos gráficos (achadas pelo teste de mutação)', () => {
    test('"mil" começa exatamente em R$ 1.000', () => {
        expect(g.formatarMoedaCurta(1000)).toBe('R$ 1 mil');
        expect(g.formatarMoedaCurta(999)).toBe('R$ 999');
    });

    test('cor lida do CSS vem sem espaços em volta', () => {
        document.documentElement.style.setProperty('--cor-destaque', '   #c96a05  ');
        expect(g.lerTokens().destaque).toBe('#c96a05');
    });

    test('sem preferência por menos movimento, a animação continua ligada', () => {
        window.matchMedia = jest.fn(() => ({ matches: false }));
        const ChartFalso = jest.fn();
        ChartFalso.defaults = { font: {} };
        g.desenharGraficos(document, ChartFalso);
        expect(ChartFalso.defaults.animation).toBeUndefined();
        delete window.matchMedia;
    });
});


describe('detalhes visuais (achados pelo teste de mutação)', () => {
    test('lê todas as cores do tema, sem espaços sobrando', () => {
        const nomes = { marca: 'marca', destaque: 'destaque', neutra: 'neutra', tinta: 'tinta', tintaSuave: 'tinta-suave',
            tintaFraca: 'tinta-fraca', linha: 'linha', grade: 'grade', superficie: 'superficie' };
        const elemento = document.createElement('div');
        Object.entries(nomes).forEach(([, css], i) => elemento.style.setProperty(`--cor-${css}`, ` #00000${i} `));
        document.body.append(elemento);

        const lidos = g.lerTokens(elemento);

        Object.keys(nomes).forEach((chave, i) => expect(lidos[chave]).toBe(`#00000${i}`));
    });

    test('linha: área preenchida clara, eixos discretos e tooltip pelo índice', () => {
        const { options, data } = g.montarConfiguracao('linha', dados, tokens, 'moeda');

        expect(data.datasets[0]).toMatchObject({ fill: true, backgroundColor: '#0d94881f' });
        expect(options).toMatchObject({
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, border: { color: tokens.linha }, ticks: { color: tokens.tintaFraca, maxRotation: 0, autoSkipPadding: 14 } },
                y: { beginAtZero: true, grid: { color: tokens.grade }, border: { display: false } },
            },
        });
    });

    test('barras: base reta, espaçamento entre grupos e tooltip pelo índice', () => {
        const config = g.montarConfiguracao('barras-agrupadas', dados, tokens, 'moeda');

        expect(config.type).toBe('bar');
        expect(config.data.datasets[0].borderSkipped).toBe('start');
        expect(config.options).toMatchObject({
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            datasets: { bar: { categoryPercentage: 0.72, barPercentage: 0.92 } },
            plugins: { legend: { display: false } },
        });
    });

    test('barras deitadas: valor no fim da barra, sem eixo de valores', () => {
        const { options } = g.montarConfiguracao('barras-horizontais', dados, tokens, 'unidades');

        expect(options).toMatchObject({
            interaction: { mode: 'nearest', axis: 'y', intersect: false },
            layout: { padding: { right: 56 } },
            scales: {
                x: { display: false, beginAtZero: true },
                y: { grid: { display: false }, border: { display: false }, ticks: { color: tokens.tintaSuave } },
            },
        });
    });

    test('mira sem tooltip ativo não desenha nada', () => {
        const ctx = contextoFalso();
        g.pluginMira(tokens).afterDatasetsDraw({ tooltip: {}, ctx });
        expect(ctx.stroke).not.toHaveBeenCalled();
    });

    test('rótulo no fim da barra centralizado na altura dela', () => {
        const ctx = contextoFalso();
        const grafico = { ctx, data: { datasets: [{ data: [3] }] }, getDatasetMeta: () => ({ data: [{ x: 10, y: 20 }] }) };
        g.pluginRotulosNoFim(tokens, { eixo: (v) => `${v}` }).afterDatasetsDraw(grafico);
        expect(ctx.textBaseline).toBe('middle');
    });

    test('pergunta ao aparelho exatamente por movimento reduzido e por tema escuro', () => {
        const consultas = [];
        window.matchMedia = jest.fn((consulta) => { consultas.push(consulta); return { matches: false, addEventListener: jest.fn() }; });
        g.desenharGraficos(document.createElement('div'), { defaults: { font: {} } });
        g.acompanharTemaDoAparelho([]);
        expect(consultas).toEqual(['(prefers-reduced-motion: reduce)', '(prefers-color-scheme: dark)']);
        expect(window.matchMedia.mock.results[1].value.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
        delete window.matchMedia;
    });
});

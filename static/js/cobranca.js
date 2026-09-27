/* Tela do Pix do plano: copiar o código e acompanhar até o Mercado Pago confirmar. */
const INTERVALO_DE_CONFERENCIA_MS = 5000;

/* Copia o "Pix copia e cola"; sem a API de área de transferência, seleciona o texto para copiar à mão. */
async function copiarPix(botao) {
    const campo = document.getElementById(botao.dataset.copiar);
    const rotulo = botao.querySelector('span') || botao;
    try {
        await navigator.clipboard.writeText(campo.value);
        rotulo.textContent = 'Código copiado!';
    } catch {
        campo.focus();
        campo.select();
        rotulo.textContent = 'Selecionado: copie com Ctrl+C ou segurando o dedo';
    }
}

/* Pergunta ao servidor pela situação da cobrança; quando deixar de estar pendente, recarrega a tela. */
function acompanharCobranca(elemento, { intervalo = INTERVALO_DE_CONFERENCIA_MS, recarregar = () => window.location.reload() } = {}) {
    const url = elemento.dataset.urlSituacao;
    let conferindo = false;
    const timer = setInterval(async () => {
        if (conferindo) return;
        conferindo = true;
        try {
            const resposta = await fetch(url, { headers: { Accept: 'application/json' }, cache: 'no-store' });
            if (!resposta.ok) return;
            const { status } = await resposta.json();
            if (status !== 'pendente') {
                clearInterval(timer);
                recarregar();
            }
        } catch {
            // Sem internet por um instante: tenta de novo na próxima volta.
        } finally {
            conferindo = false;
        }
    }, intervalo);
    return () => clearInterval(timer);
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-acompanhar-cobranca]').forEach((elemento) => acompanharCobranca(elemento));
});

/* istanbul ignore else */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { copiarPix, acompanharCobranca };
}

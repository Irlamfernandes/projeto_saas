/* Registra o service worker (app instalável no celular). Fica num arquivo próprio porque a política de segurança
   do site não deixa rodar <script> escrito dentro do HTML. O endereço do sw.js vem em data-sw (com a versão no nome). */
function registrarServiceWorker(script = document.currentScript, navegador = globalThis.navigator, janela = globalThis) {
    if (!script || !('serviceWorker' in navegador)) return;
    janela.addEventListener('load', () => navegador.serviceWorker.register(script.dataset.sw));
}

registrarServiceWorker();

/* istanbul ignore else */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { registrarServiceWorker };
}

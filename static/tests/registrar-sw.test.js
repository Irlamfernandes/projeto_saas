/**
 * @jest-environment jsdom
 */
const { registrarServiceWorker } = require('../js/registrar-sw.js');

describe('registro do service worker', () => {
    const script = () => {
        const tag = document.createElement('script');
        tag.dataset.sw = '/static/sw.abc123.js';
        return tag;
    };

    test('registra o endereço do data-sw quando a página termina de carregar', () => {
        const register = jest.fn();
        const janela = new EventTarget();
        registrarServiceWorker(script(), { serviceWorker: { register } }, janela);

        expect(register).not.toHaveBeenCalled();
        janela.dispatchEvent(new Event('load'));
        expect(register).toHaveBeenCalledWith('/static/sw.abc123.js');
    });

    test('navegador sem service worker ou script sem a tag: não faz nada', () => {
        const janela = new EventTarget();
        janela.addEventListener = jest.fn();
        registrarServiceWorker(script(), {}, janela);
        registrarServiceWorker(null, { serviceWorker: {} }, janela);
        expect(janela.addEventListener).not.toHaveBeenCalled();
    });
});

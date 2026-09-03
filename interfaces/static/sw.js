self.addEventListener('install', (event) => {
    console.log('Service Worker instalado com sucesso.');
});

self.addEventListener('fetch', (event) => {
    event.respondWith(fetch(event.request));
});
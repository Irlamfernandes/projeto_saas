// Linter do JavaScript (roda no CI e em `make lint`). Regras recomendadas: acham bug, não impõem estilo.
const js = require('@eslint/js');
const globals = require('globals');

module.exports = [
    { ignores: ['static/vendor/**', 'static/css/**', 'staticfiles/**', 'coverage/**', 'node_modules/**', 'venv/**', '.venv/**'] },
    js.configs.recommended,
    {
        // Scripts clássicos do navegador; o `module.exports` no fim de cada um só existe para o Jest.
        files: ['static/js/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: { ...globals.browser, module: 'writable', Chart: 'readonly' },
        },
    },
    {
        files: ['static/tests/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: { ...globals.browser, ...globals.node, ...globals.jest },
        },
    },
    {
        files: ['eslint.config.js', 'tailwind.config.js'],
        languageOptions: { sourceType: 'commonjs', globals: globals.node },
    },
];

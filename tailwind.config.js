/** @type {import('tailwindcss').Config} */
module.exports = {
  // Só os arquivos do projeto: um glob amplo varreria venv/ e node_modules/.
  content: [
    "./interfaces/templates/**/*.html",
    "./infrastructure/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      // Tema "Petróleo": verde-azulado calmo para uso prolongado, âmbar só em destaques.
      // Pares de gráfico validados para daltonismo (marca x destaque).
      colors: {
        marca: { 50: '#f0f9f8', 100: '#e6f4f2', 200: '#c4e6e1', 500: '#0d9488', 600: '#0f766e', 700: '#115e59' },
        destaque: { 50: '#fbf0e3', 100: '#f7e0c4', 500: '#c96a05', 700: '#8a4a05' },
        tinta: { DEFAULT: '#16211f', suave: '#4b5b58', fraca: '#7c8a87' },
        fundo: '#f4f7f6',
        linha: '#e2e9e7',
        grade: '#edf1f0',
        // Status: fixos, sempre acompanhados de ícone + texto
        bom: { DEFAULT: '#0ca30c', texto: '#0b6b1d', suave: '#e8f6e8' },
        alerta: { DEFAULT: '#fab219', texto: '#8a5a00', suave: '#fff5dc' },
        critico: { DEFAULT: '#d03b3b', texto: '#a42a2a', suave: '#fdeaea' },
      },
      fontFamily: {
        sans: ['Figtree', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        titulo: ['"Bricolage Grotesque"', 'Figtree', 'system-ui', 'sans-serif'],
      },
      borderRadius: { cartao: '1rem', controle: '0.7rem' },
    },
  },
  plugins: [],
}

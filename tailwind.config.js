/** @type {import('tailwindcss').Config} */

// Cor que troca com o tema: lê os canais RGB da variável e mantém a opacidade do Tailwind (bg-marca-600/40).
const cor = (nome) => `rgb(var(--${nome}) / <alpha-value>)`;

module.exports = {
  // Só os arquivos do projeto: um glob amplo varreria venv/ e node_modules/.
  content: [
    "./interfaces/templates/**/*.html",
    "./infrastructure/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    // Pontos de quebra em em (e não px): com letra grande ou zoom, o layout troca para o de celular na hora certa.
    screens: { sm: '40em', md: '48em', lg: '64em', xl: '80em', '2xl': '96em' },
    extend: {
      // Tema "Petróleo": verde-azulado calmo para uso prolongado, âmbar só em destaques.
      // Pares de gráfico validados para daltonismo (marca x destaque).
      // As cores que mudam no modo escuro vêm de variáveis CSS (static/css/input.css, canais RGB para aceitar /opacidade).
      colors: {
        marca: {
          50: cor('marca-50'), 100: cor('marca-100'), 200: cor('marca-200'),
          500: cor('marca-500'), 600: cor('marca-600'), 700: cor('marca-700'),
          // Fixo nos dois temas: fundo escuro com texto branco (lateral do login, botão ao passar o mouse)
          profundo: '#115e59',
        },
        destaque: { 50: cor('destaque-50'), 100: cor('destaque-100'), 500: cor('destaque-500'), 700: cor('destaque-700') },
        // CorsariosCode (quem desenvolveu o sistema): tirado da logo
        corsario: { fundo: '#05080f', claro: '#d9d8d6', azul: '#6f9fd8', 'azul-escuro': cor('corsario-azul-escuro') },
        tinta: { DEFAULT: cor('tinta'), suave: cor('tinta-suave'), fraca: cor('tinta-fraca') },
        fundo: cor('fundo'),
        superficie: cor('superficie'),
        linha: cor('linha'),
        grade: cor('grade'),
        // Véu escuro atrás de janelas e da galeria de fotos: escuro nos dois temas
        veu: '#0b1211',
        // Status: sempre acompanhados de ícone + texto
        bom: { DEFAULT: cor('bom'), texto: cor('bom-texto'), suave: cor('bom-suave') },
        alerta: { DEFAULT: cor('alerta'), texto: cor('alerta-texto'), suave: cor('alerta-suave') },
        critico: { DEFAULT: cor('critico'), texto: cor('critico-texto'), suave: cor('critico-suave') },
      },
      fontFamily: {
        sans: ['Figtree', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        titulo: ['"Bricolage Grotesque"', 'Figtree', 'system-ui', 'sans-serif'],
      },
      // Anel de foco: a folga entre o campo e o anel usa o fundo da página (branca no escuro ficaria um clarão)
      ringOffsetColor: { DEFAULT: cor('fundo') },
      borderRadius: { cartao: '1rem', controle: '0.7rem' },
    },
  },
  plugins: [],
}

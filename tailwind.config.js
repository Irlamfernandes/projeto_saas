/** @type {import('tailwindcss').Config} */
module.exports = {
  // Só os arquivos do projeto: um glob amplo varreria venv/ e node_modules/.
  content: [
    "./interfaces/templates/**/*.html",
    "./infrastructure/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

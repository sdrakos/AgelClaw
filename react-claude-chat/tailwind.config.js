/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'claude': {
          50: '#fef5ee',
          100: '#fde8d7',
          200: '#fbcdae',
          300: '#f7ab7a',
          400: '#f37e44',
          500: '#f05b1f',
          600: '#e14115',
          700: '#ba2f13',
          800: '#942718',
          900: '#782316',
        }
      }
    },
  },
  plugins: [],
}

module.exports = {
  purge: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class', // or 'media' or 'class'
  theme: {
    extend: {
      colors: {
        'dark-gray': '#1E1E1E',
        'medium-gray': '#2D2D2D',
        'light-gray': '#3E3E3E',
        'highlight-gray': '#4A4A4A',
        'custom-red': '#FF4B4B',
        'custom-blue': '#3B82F6',
      },
      fontFamily: {
        sans: ['Arial', 'sans-serif'],
      },
    },
  },
  variants: {
    extend: {},
  },
  plugins: [],
}
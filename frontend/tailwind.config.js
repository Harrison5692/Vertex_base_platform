/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // References the CSS variable set dynamically by clientConfig.jsx
        // from client.config.json — brand-primary-500 / -600 update per
        // deployment with zero rebuild, since it's a runtime CSS var, not
        // a compile-time Tailwind color.
        brand: {
          DEFAULT: 'var(--primary-color)',
          50: 'color-mix(in srgb, var(--primary-color) 10%, white)',
          100: 'color-mix(in srgb, var(--primary-color) 20%, white)',
          500: 'var(--primary-color)',
          600: 'color-mix(in srgb, var(--primary-color) 85%, black)',
          700: 'color-mix(in srgb, var(--primary-color) 70%, black)',
        },
      },
    },
  },
  plugins: [],
}


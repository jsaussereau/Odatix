/** @type {import('tailwindcss').Config} */
module.exports = {
    presets: [require('./themes/hugo-saasify-theme/tailwind.config.js')],
    content: [
      "./themes/hugo-saasify-theme/layouts/**/*.html",
      "./layouts/**/*.html",
      "./content/**/*.{html,md}"
    ],
    theme: {
      extend: {
        fontFamily: {
          sans: ['Inter', 'system-ui', 'sans-serif'],
          heading: ['Plus Jakarta Sans', 'sans-serif'],
          mono: [
            'JetBrains Mono',
            'DejaVu Sans Mono',
            'Noto Sans Mono',
            'ui-monospace',
            'SFMono-Regular',
            'Menlo',
            'Monaco',
            'Consolas',
            'Liberation Mono',
            'Courier New',
            'monospace',
          ],
        },
      },
    },
    plugins: [
      require('@tailwindcss/forms'),
      require('@tailwindcss/typography'),
    ],
    safelist: [
      {
        pattern: /^data-badge-/,
      },
    ],
  }
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'var(--c-border)',
        input: 'var(--c-border)',
        ring: 'var(--c-primary)',
        background: 'var(--c-bg)',
        foreground: 'var(--c-text)',
        primary: {
          DEFAULT: 'var(--c-primary)',
          foreground: '#ffffff',
        },
        secondary: {
          DEFAULT: 'var(--c-surface2)',
          foreground: 'var(--c-text)',
        },
        destructive: {
          DEFAULT: 'var(--c-red)',
          foreground: '#ffffff',
        },
        muted: {
          DEFAULT: 'var(--c-surface2)',
          foreground: 'var(--c-text2)',
        },
        accent: {
          DEFAULT: 'var(--c-surface2)',
          foreground: 'var(--c-text)',
        },
        card: {
          DEFAULT: 'var(--c-surface)',
          foreground: 'var(--c-text)',
        },
        popover: {
          DEFAULT: 'var(--c-surface)',
          foreground: 'var(--c-text)',
        },
      },
      borderRadius: {
        lg: '0.625rem',
        md: '0.5rem',
        sm: '0.375rem',
      },
    },
  },
  plugins: [],
};

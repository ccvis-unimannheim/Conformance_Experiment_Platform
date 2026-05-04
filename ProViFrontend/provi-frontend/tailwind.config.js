/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background:               "var(--background)",
        foreground:               "var(--foreground)",
        primary:                  '#0f3463',
        'primary-container':      '#2b4b7b',
        'on-primary':             '#ffffff',
        secondary:                '#5b5f62',
        surface:                  '#f8f9fa',
        'surface-container':      '#edeeef',
        'surface-container-low':  '#f3f4f5',
        'surface-container-lowest':'#ffffff',
        'on-surface':             '#191c1d',
        'on-surface-variant':     '#43474f',
        'border-subtle':          '#dee2e6',
        'outline-variant':        '#c4c6d0',
        'surface-variant':        '#e1e3e4',
        error:                    '#ba1a1a',
        'error-container':        '#ffdad6',
      },
      borderRadius: {
        DEFAULT: '0.125rem',
        lg:      '0.25rem',
        xl:      '0.5rem',
        full:    '0.75rem',
      },
      fontFamily: {
        h1:       ['Inter', 'sans-serif'],
        'body-lg':['Inter', 'sans-serif'],
        button:   ['Inter', 'sans-serif'],
      },
      fontSize: {
        h1:       ['32px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        'body-lg':['16px', { lineHeight: '1.6', fontWeight: '400' }],
        button:   ['14px', { lineHeight: '1',   fontWeight: '600' }],
      },
    },
  },
  plugins: [],
};

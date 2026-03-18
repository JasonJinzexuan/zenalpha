/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0a12',
          card: '#10101c',
          hover: '#161626',
          border: '#1e1e3a',
        },
        accent: {
          cyan: '#00f0ff',
          green: '#00ff9f',
          red: '#ff3366',
          magenta: '#ff00aa',
          yellow: '#ffcc00',
          orange: '#ff9500',
          purple: '#b040ff',
          blue: '#4488ff',
        },
        text: {
          primary: '#e0e0f0',
          dim: '#666680',
          muted: '#444460',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      animation: {
        pulse_slow: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        blink: 'blink 1.2s step-end infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0 },
        },
      },
    },
  },
  plugins: [],
}

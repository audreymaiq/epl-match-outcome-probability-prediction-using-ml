import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        pl: {
          purple: '#3d195b',
          'purple-light': '#5a2d82',
          'purple-dark': '#2a1140',
          green: '#00ff85',
          'green-dark': '#00cc6a',
          white: '#ffffff',
          'off-white': '#f8f6fb',
          'gray-light': '#e8e0f0',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'pl-gradient': 'linear-gradient(135deg, #3d195b 0%, #5a2d82 100%)',
      },
    },
  },
  plugins: [],
}

export default config

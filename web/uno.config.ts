import { defineConfig, presetWind3, presetIcons, transformerDirectives, transformerVariantGroup } from 'unocss'

export default defineConfig({
  presets: [
    presetWind3(),
    presetIcons({
      scale: 1.2,
      warn: true,
      extraProperties: {
        display: 'inline-block',
        'vertical-align': 'middle',
      },
    }),
  ],
  transformers: [transformerDirectives(), transformerVariantGroup()],
  theme: {
    colors: {
      // 方案 B 暖色杂志：奶油纸底 + 陶土橘 + 暖墨
      void: '#fdfbf7',
      base: '#f7f2e9',
      elevated: '#efe7d8',
      surface: '#ffffff',
      code: '#f3ede2',
      accent: {
        DEFAULT: '#b45309',
        bright: '#d97706',
        deep: '#7c3a06',
        soft: '#fdf3e3',
        line: '#f0d5ac',
        // 兼容旧类名
        blue: '#b45309',
        cyan: '#c2670f',
      },
      ok: '#4d7c0f',
      warn: '#a16207',
      danger: '#b4342a',
      info: '#2f6f9e',
      ink: '#26211b',
      t1: '#26211b',
      t2: '#5f5648',
      t3: '#94897a',
      t4: '#bdb2a1',
    },
    fontFamily: {
      sans: "'Satoshi', 'Inter', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif",
      display: "'Clash Display', 'Satoshi', Georgia, 'PingFang SC', serif",
      serif: "'Zodiak', 'Noto Serif SC', 'STSong', Georgia, serif",
      mono: "'Synonym', 'JetBrains Mono', 'SF Mono', Consolas, monospace",
    },
  },
  shortcuts: {
    // 浅色主题：卡片是白底 + 暖线 + 柔影，不再是玻璃
    card: 'bg-white border border-[#e8dfd1] rounded-[16px] shadow-[0_1px_2px_rgba(38,33,27,.05),0_6px_18px_rgba(38,33,27,.05)]',
    'card-hover': 'hover:border-[#dbcfbc] transition-all duration-200',
    'label-xs': 'text-[11px] uppercase tracking-[0.1em] text-t3 font-600',
    'mono-num': 'font-mono tabular-nums',
  },
  safelist: [
    'i-lucide-scan-line', 'i-lucide-library', 'i-lucide-cloud-sun', 'i-lucide-map-pin',
    'i-lucide-user-round', 'i-lucide-calendar', 'i-lucide-database', 'i-lucide-file-bar-chart',
    'i-lucide-check', 'i-lucide-x', 'i-lucide-chevron-down', 'i-lucide-chevron-up',
    'i-lucide-arrow-up', 'i-lucide-square', 'i-lucide-plus', 'i-lucide-message-circle',
    'i-lucide-message-square', 'i-lucide-panel-right', 'i-lucide-file-text', 'i-lucide-sparkles',
    'i-lucide-circle-alert', 'i-lucide-loader-circle', 'i-lucide-wifi-off', 'i-lucide-brain',
    'i-lucide-pencil', 'i-lucide-trash-2', 'i-lucide-search', 'i-lucide-wrench',
    'i-lucide-droplets', 'i-lucide-trending-up', 'i-lucide-filter', 'i-lucide-refresh-cw',
  ],
})

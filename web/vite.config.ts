import UnoCSS from '@unocss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  // 注意：必须从 '@unocss/vite' 直接引入。
  // `unocss/vite` 在 Vite 8 + 本依赖树组合下会返回空插件数组（静默失效）。
  plugins: [UnoCSS(), vue()],
  server: {
    // 显式绑定 IPv4：默认只监听 localhost(::1) 时，127.0.0.1 访问会失败
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // 开发期把 /api 代理到 FastAPI 适配层，避免 CORS 与硬编码地址
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // three.js 体积大（~600KB），单独成 chunk：
        // 配合 ParticleField 的异步加载，首屏完全不下载它，且长期缓存友好。
        manualChunks(id) {
          if (id.includes('node_modules/three')) return 'three'
          if (id.includes('node_modules/markdown-it') || id.includes('node_modules/uc.micro')
            || id.includes('node_modules/mdurl') || id.includes('node_modules/linkify')
            || id.includes('node_modules/punycode') || id.includes('node_modules/argparse')) {
            return 'markdown'
          }
          return undefined
        },
      },
    },
  },
})

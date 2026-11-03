import { createApp } from 'vue'
// UnoCSS 66+ 的入口模块是 `uno.css`（旧版的 `virtual:uno.css` 已移除）
import 'uno.css'
// Fontshare 字体（本地自托管，须先于 tokens.css）
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'
import App from './App.vue'

createApp(App).mount('#app')

# 智扫通 · 前端

面向消费者（ToC）的扫地机器人智能客服 Web 界面。
把 LangChain ReAct Agent 的**思考过程**变成可观看的界面——这是本产品的核心设计主张。

> **当前视觉**：方案 B「暖色杂志 Editorial Warmth」——奶油纸底、暖墨文字、陶土橘强调、
> Zodiak 衬线正文。完整规范见 `../.superdesign/design-system.md`。

---

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 框架 | Vue 3.5（`<script setup>` + TS） | Composition API |
| 构建 | Vite 8 | dev server + 生产构建 + 手动分包 |
| 样式 | UnoCSS 66（presetWind3 + presetIcons） | 原子类 + Lucide 图标 |
| 字体 | **Fontshare**（Clash Display / Zodiak / Satoshi / Synonym） | 本地自托管 `public/fonts/` |
| 背景 | **Three.js 0.186** GPU 粒子 | 异步加载，不进首屏关键路径 |
| Markdown | markdown-it | 助手回答渲染 |

> 没有引入任何 UI 组件库——所有组件按 `design-system.md` 从零实现，以保证视觉一致性。

---

## 字体来源（本地自托管）

全部取自 [fontshare.com](https://fontshare.com)（Indian Type Foundry，免费商用），
已下载 woff2 至 `public/fonts/`，**不依赖外网 CDN**：

| 字族 | 用途 | 字重 |
|---|---|---|
| Clash Display | 品牌字、大标题、正文小标题 | 400/500/600/700 |
| Zodiak | **助手回答正文**（衬线） | 400 |
| Satoshi | UI 无衬线（导航/按钮/标签） | 400/500/700 |
| Synonym | 等宽（工具名、JSON、数字） | 400/500 |

声明在 `src/styles/fonts.css`，`@font-face` 指向 `/fonts/*.woff2`。
中文兜底：`Noto Serif SC → STSong → SimSun`（衬线）、`PingFang SC → Microsoft YaHei`（无衬线）。

> `main.ts` 里的引入顺序不可颠倒：`uno.css → fonts.css → tokens.css → base.css`。

---

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器（需要后端已运行在 127.0.0.1:8010）
npm run dev

# 3. 生产构建
npm run build

# 4. 预览构建产物
npm run preview
```

访问 http://127.0.0.1:5173

> **注意**：开发服务器已配置 `/api` → `http://127.0.0.1:8010` 的代理，
> 因此必须先启动后端（见项目根目录 `README-FRONTEND.md`）。

---

## 打包与性能

`vite.config.ts` 里做了手动分包，因为 three.js 体积大且粒子是纯装饰：

| chunk | 体积 | 加载时机 |
|---|---|---|
| `index` | 116 KB（gzip 44 KB） | 首屏 |
| `markdown` | 100 KB（gzip 41 KB） | 首屏（答案渲染需要） |
| `three` | 525 KB（gzip 130 KB） | **异步**，不阻塞首屏 |
| `ParticleField` | 3.8 KB | 异步 |

`ParticleField` 用 `defineAsyncComponent` 包裹，three.js 完全不进首屏关键路径。
**若不做这个拆分，首屏 JS 会是 741 KB。**

---

## 目录结构

```
web/
├── index.html
├── vite.config.ts          # Vite 配置（/api 代理 + 手动分包）
├── uno.config.ts           # UnoCSS 主题（与 tokens.css 同步）
├── public/
│   └── fonts/              # Fontshare woff2（10 个文件，约 224 KB）
└── src/
    ├── main.ts             # 入口（引入顺序见上）
    ├── App.vue             # 应用外壳（三栏 + 健康检查 + 会话 + 两个抽屉）
    ├── api/
    │   ├── client.ts       # HTTP 客户端 + SSE 帧解析器
    │   └── types.ts        # 与后端契约一一对应的类型
    ├── composables/
    │   └── useChat.ts      # 对话状态机（SSE 聚合 + 落库）
    ├── views/
    │   └── ChatView.vue    # 智能问答主视图
    ├── components/
    │   ├── background/ParticleField.vue    # Three.js GPU 粒子
    │   ├── chat/           # MessageBubble · ThinkingBlock
    │   │                   # ToolCallCard · ChatComposer
    │   ├── layout/         # TopBar · SideBar · InspectorPanel
    │   ├── knowledge/KnowledgeDrawer.vue   # 知识库检索抽屉
    │   ├── analytics/AnalyticsDrawer.vue   # 数据看板抽屉
    │   └── ui/             # StatusPill · BrandMark（品牌标识单一来源）
    └── styles/
        ├── fonts.css       # @font-face（Fontshare 本地自托管）
        ├── tokens.css      # 设计令牌（唯一色彩来源）
        └── base.css        # 重置 + 全局规则
```

---

## 品牌标识（BrandMark）

`components/ui/BrandMark.vue` 是标识的**唯一来源**，`public/favicon.svg` 与
`public/icons.svg` 是其静态导出（改标识必须三处同步）。

- **形态**：两圆错位套色叠印，交叠区 `#b45309` × `#26211b` 压出 `#1b0b01`，
  中心留白点为机器人本体。双关：清扫覆盖 × 对话气泡。
- **叠印用 `clipPath` 显式绘制，不用 `mix-blend-mode`**——后者在 favicon
  光栅器与旧 Safari 下会退化。
- **clipPath id 用 `useId()` 保证每实例唯一**，否则多实例互相串引用。
- **容器底色必须用 `--bg-void`**（标识自带橘色，容器再上橘会撞色）。
- **头像只渲染一处**：`MessageBubble` 有 `showAvatar` 开关，`ChatView`
  外层已带头像时传 `false`，否则同一回合出现两个标识。

### SVG 陷阱（做线性笔画变体时务必注意）

渐变默认 `gradientUnits="objectBoundingBox"`，在**零面积 bbox** 上无法计算——
纯水平线（高 0）或纯竖直线（宽 0）的描边会整体不渲染，且**没有任何报错**。
必须写成 `gradientUnits="userSpaceOnUse"` 并用绝对坐标。

> 着色器与绘制验证的两个同类陷阱见下方「7. Three.js 粒子」。

---

## 侧栏拖拽缩放

把手实装在 `SideBar.vue` 内部，宽度状态由 `App.vue` 持有并持久化。

| 项 | 值 |
|---|---|
| 范围 | 200–420px，默认 260 |
| 吸附 | 拖到 <160px → 72px 图标栏（`rail` 态隐藏文字） |
| 持久化 | `localStorage['zs.sidebar.width']` |
| 复位 | 双击把手；键盘 `Home` |
| 键盘 | `←/→` 8px、`Shift+←/→` 32px、`End` 到 420 |
| 无障碍 | `role="separator"` + `aria-valuenow/min/max` |
| 拖拽期 | `body` 设 `user-select:none` + `cursor:col-resize`；把手 `touch-action:none` |

两个实现要点：

1. **把手骑在边界上**（`right:-5px`，宽 11px，绝对定位），
   默认只露侧栏自身的 1px 分隔线，hover/拖拽才显出 2px 陶土橘 + 握柄——不额外占布局宽度。
2. **宽度必须经 CSS 变量 `--sb-w` 传入，不能用内联 `width`**——
   内联样式优先级高于 `@media`，会让 ≤1024px 的 72px 收窄规则失效。

---

## 核心设计决策

### 1. 为什么用 fetch 而不是 EventSource

`EventSource` 只支持 GET，无法发送 POST body，且会自动重连（问答场景重连等于重复生成）。
因此 `api/client.ts` 手写 SSE 帧解析，兼容 `\r\n` / `\n` 与多行 `data:`。

### 2. 思考与答案如何区分

后端以 `stream_mode="messages"` 输出 token 级增量，**同一格式**里既有思考也有答案。
判定规则：**工具调用全部结束后，模型输出的文本才是最终答案**；此前都是思考。

### 3. 思考为什么要按 step 合并

一次回答会产生 150+ 个 `thinking` 事件（逐字）。若逐条渲染会有 150 行，不可读。
`useChat.ts` 按 `step` 聚合，通常只剩 1–3 段，正好对应 ReAct 的 1–3 轮思考。

### 4. 自动滚动为什么用 MutationObserver

消息对象是父组件 `reactive` 数组的元素，经 props 传入后，深层字段变更在 `watch`
getter 里不一定被追踪（实测"完全不跟随"）。直接观察 DOM 变化最可靠。

同时：容器**不能**设 `scroll-behavior: smooth`——流式高频更新时平滑动画会互相打断，
表现为完全不滚动。改用 `scrollTo({ behavior: 'auto' })`。

### 5. Markdown 预处理

模型常输出 `**"控水"**`（加粗紧贴中文引号），CommonMark 的定界符规则会判定不闭合，
原样输出星号。`MessageBubble.vue` 的 `normalizeMarkdown()` 把引号移到加粗外侧，
并对 `***xxx***` 做降级处理。

### 6. 浅色主题不能沿用深色主题的手法（换肤时踩到的真实教训）

| 深色主题手法 | 在浅色底上的后果 | 正确做法 |
|---|---|---|
| `backdrop-filter` 做玻璃 | 不透明底色上**完全不起作用**，白耗 GPU | 只保留在遮罩层与半透明顶栏 |
| 低透明色做"发光" | 变成洗掉的浅色，按钮失去力度 | 主按钮改**实心渐变 + 柔投影** |
| 亮色做文字强调 | `#d97706` on cream 仅 3.1:1，不达标 | 文字用 `--accent-core`（5.0:1） |
| 层级靠边框亮度 | 白底上边框差异看不出来 | 改用**白卡 + 暖细线 + 柔投影** |

### 7. Three.js 粒子两个必须注意的实现细节

1. **`attribute` 只能在顶点着色器声明**。片元里要用必须经 `varying` 传递，
   否则着色器编译失败且**没有任何可见报错**，表现为整块背景什么都不画。
2. **透视衰减必须带焦距常数**。`gl_PointSize *= 1.0 / -mv.z` 在相机距离 ~100 时
   算出的点径只有 ~1px，等于看不见；需要
   `uSize * aScale * uPixelRatio * (uFocal / dist)`。

另外：浅色底要用 `NormalBlending`，**不能用 `AdditiveBlending`**——
加法混合在奶油色上会把粒子冲成发白的虚影。

> 验证粒子是否真的在画，**不能**用 `gl.readPixels`：
> WebGL 默认 `preserveDrawingBuffer: false`，合成后缓冲区已被清空，readPixels 必然返回全 0。
> 可靠方法是临时把 canvas 的 CSS `opacity` 调到 2.5 + `contrast(2.5)` 再截图观察。

### 8. 响应式断点

| 宽度 | 布局 |
|---|---|
| >1280px | 三栏并排，检查器默认展开 |
| ≤1280px | 检查器转覆盖式抽屉，**默认收起**，可关闭 |
| ≤1024px | 侧栏收窄为图标栏 |
| ≤768px | 单栏，侧栏与检查器隐藏 |

---

## 无障碍与性能

- 所有动效遵守 `prefers-reduced-motion`（粒子降级为静态一帧）
- 粒子在 `document.hidden` 时暂停 rAF，卸载时 `dispose()` 释放 GPU 资源
- WebGL 不可用时静默降级，页面照常工作
- 图标均为 Lucide 线性图标（`aria-hidden` 或配合 `aria-label`）
- 文字对比度逐条核对 WCAG AA：正文 14.8:1、次要 7.0:1、强调 5.0:1
- 中文输入法组合期间（`isComposing`）不触发发送

---

## 设计规范

完整规范见 `../.superdesign/design-system.md`，要点：

- **色彩**：奶油纸底 `#fdfbf7`，暖墨文字 `#26211b`，陶土橘强调 `#b45309`
- **字体**：Clash Display（标题）+ Zodiak（正文衬线）+ Satoshi（UI）+ Synonym（等宽）
- **层级**：白卡 + 暖色细线 + 极柔暖灰投影（不用发光、不用无效模糊）
- **动效即状态**：思考中扫描线、工具竖条变色、流式光标呼吸

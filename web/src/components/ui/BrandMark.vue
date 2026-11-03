<script setup lang="ts">
/**
 * BrandMark —— 智扫通品牌标识（方案 G · 套色叠印）
 *
 * 形态语言：两个圆错位叠印，交叠处压出第三色，
 * 像丝网印刷没对准留下的手作痕迹。
 * 双关：清扫覆盖的轨迹 × 对话气泡。
 *
 * 为什么不用 mix-blend-mode：
 *   叠印色用 CSS 混合模式实现的话，在 favicon、部分 SVG 光栅器与
 *   旧版 Safari 下会退化或不被支持。这里改用 clipPath 把交叠区
 *   显式画出来，任何渲染器结果都一致。
 *
 * 三个变体：
 *   color —— 标准三色（陶土橘 + 暖墨 + 叠印深）
 *   mono  —— 单色，跟随 currentColor（深浅底通用、打印）
 *   paper —— 反白，用于实心橘底之上
 */
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    size?: number
    variant?: 'color' | 'mono' | 'paper'
  }>(),
  { size: 24, variant: 'color' },
)

/** 叠印三色（与设计系统 token 同值，SVG 内联需字面量） */
const INK_ORANGE = '#b45309'   // --accent-core
const INK_DARK = '#26211b'     // --text-primary
const INK_OVERPRINT = '#1b0b01' // 上两色 multiply 的实际结果
const PAPER = '#fdfbf7'        // --bg-void

/** 每个实例的 clipPath id 必须唯一，否则多实例会互相串引用 */
const clipId = computed(() => `bm-clip-${useId().replace(/[^a-zA-Z0-9]/g, '')}`)

const leftFill = computed(() => {
  if (props.variant === 'mono') return 'currentColor'
  if (props.variant === 'paper') return PAPER
  return INK_ORANGE
})
const rightFill = computed(() => {
  if (props.variant === 'mono') return 'currentColor'
  if (props.variant === 'paper') return PAPER
  return INK_DARK
})
const overFill = computed(() => {
  if (props.variant === 'mono') return 'currentColor'
  if (props.variant === 'paper') return PAPER
  return INK_OVERPRINT
})
/** 中心留白点：彩色版是纸色；单色版要"挖空"所以用 paper；反白版用橘色 */
const dotFill = computed(() => {
  if (props.variant === 'mono') return PAPER
  if (props.variant === 'paper') return INK_ORANGE
  return PAPER
})
/** 单色版靠透明度区分层次，避免三块同色糊成一团 */
const leftOpacity = computed(() => (props.variant === 'mono' ? 0.55 : 1))
const rightOpacity = computed(() => (props.variant === 'mono' ? 0.85 : 1))
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    class="brand-mark"
  >
    <defs>
      <clipPath :id="clipId">
        <circle cx="9.2" cy="12" r="7.1" />
      </clipPath>
    </defs>

    <!-- 左圆 -->
    <circle cx="9.2" cy="12" r="7.1" :fill="leftFill" :opacity="leftOpacity" />
    <!-- 右圆 -->
    <circle cx="14.8" cy="12" r="7.1" :fill="rightFill" :opacity="rightOpacity" />
    <!-- 叠印区：右圆裁进左圆范围，压出第三色 -->
    <circle
      cx="14.8"
      cy="12"
      r="7.1"
      :fill="overFill"
      :clip-path="`url(#${clipId})`"
      :opacity="variant === 'mono' ? 1 : undefined"
    />
    <!-- 中心留白：机器人本体 -->
    <circle cx="12" cy="12" r="1.55" :fill="dotFill" />
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  flex-shrink: 0;
}
</style>

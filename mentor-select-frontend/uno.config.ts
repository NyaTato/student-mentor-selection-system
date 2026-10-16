import { defineConfig, presetUno, presetAttributify } from 'unocss'

export default defineConfig({
  presets: [presetUno(), presetAttributify()],
  // 主题色通过 CSS 变量控制，UnoCSS 仅提供工具类
  theme: {},
})

import eslintPluginVue from "eslint-plugin-vue"
import tseslint from "typescript-eslint"

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  ...tseslint.configs.recommended,
  ...eslintPluginVue.configs["flat/essential"],
  {
    files: ["**/*.{ts,vue}"],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/require-default-prop": "off",
    },
  },
)

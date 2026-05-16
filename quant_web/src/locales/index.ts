import { createI18n } from "vue-i18n";
import en from "../locales/en-US.json";
import zh from "../locales/zh-CN.json";

const messages = {
  "en-US": en,
  "zh-CN": zh,
};

const i18n = createI18n({
  legacy: false,
  locale: "zh-CN",
  fallbackLocale: "en-US",
  messages,
});

export default i18n;

import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import kn from './locales/kn.json'
import hi from './locales/hi.json'
import te from './locales/te.json'

const FONT_HREF_BY_LANGUAGE = {
  kn: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Kannada:wght@400;500;600;700&display=swap',
  hi: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap',
  te: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;500;600;700&display=swap',
}

function updateLanguageAttributes(language) {
  document.documentElement.lang = language
  document.documentElement.setAttribute('data-lang', language)
}

export function loadGoogleFont(language) {
  const href = FONT_HREF_BY_LANGUAGE[language]
  if (!href) {
    return
  }

  const selector = `link[data-farmshield-font='${language}']`
  const existingLink = document.head.querySelector(selector)
  if (existingLink) {
    return
  }

  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = href
  link.setAttribute('data-farmshield-font', language)
  document.head.appendChild(link)
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: en },
      kn: { common: kn },
      hi: { common: hi },
      te: { common: te },
    },
    supportedLngs: ['en', 'kn', 'hi', 'te'],
    fallbackLng: 'en',
    ns: ['common'],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'fs_language',
      caches: ['localStorage'],
    },
  })

const resolvedLanguage = i18n.resolvedLanguage || i18n.language || 'en'
updateLanguageAttributes(resolvedLanguage)
loadGoogleFont(resolvedLanguage)

i18n.on('languageChanged', (language) => {
  updateLanguageAttributes(language)
  loadGoogleFont(language)
})

export default i18n

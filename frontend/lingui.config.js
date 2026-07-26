import { formatter } from '@lingui/format-po';

export default {
  locales: [
    'de',
    'en',
    'es',
    'fr',
    'it',
    'ja',
    'ru',
    'zh_Hans',
    'zh_Hant',
    'pseudo-LOCALE',
  ],
  catalogs: [
    {
      path: 'src/locales/{locale}/messages',
      include: ['src'],
      exclude: ['**/node_modules/**', './dist/**'],
    },
  ],
  format: formatter({ lineNumbers: false }),
  orderBy: 'origin',
  sourceLocale: 'en',
  fallbackLocales: {
    default: 'en',
    'pseudo-LOCALE': 'en',
  },
};

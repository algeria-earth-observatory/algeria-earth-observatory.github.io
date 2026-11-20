/**
 * Multilingual infrastructure.
 *
 * English is the only published language. French and Arabic dictionaries are
 * prepared with the same keys but are NOT routed until complete translations
 * have been reviewed by fluent scientific reviewers (see CONTRIBUTING.md,
 * "Translations"). Arabic pages must render with dir="rtl" — the Base layout
 * already switches direction from the `lang` prop.
 */
export const LOCALES = {
  en: { label: 'English', dir: 'ltr', published: true },
  fr: { label: 'Français', dir: 'ltr', published: false },
  ar: { label: 'العربية', dir: 'rtl', published: false },
} as const;
export type Locale = keyof typeof LOCALES;

export const ui = {
  en: {
    'nav.data': 'Data',
    'nav.map': 'Map',
    'nav.methods': 'Methods',
    'nav.contribute': 'Contribute',
    'nav.community': 'Community',
    'nav.about': 'About',
    'status.available': 'Available',
    'status.external': 'External source',
    'status.in-preparation': 'In preparation',
    'status.archived': 'Archived',
    'action.access': 'Access at source',
    'action.download': 'Download',
    'action.copyCitation': 'Copy citation',
  },
  // Translation slots: intentionally empty until reviewed translations exist.
  fr: {},
  ar: {},
} as const;

export function t(locale: Locale, key: keyof (typeof ui)['en']): string {
  const dict = ui[locale] as Partial<Record<string, string>>;
  return dict[key] ?? ui.en[key];
}

export const publishedLocales = (Object.keys(LOCALES) as Locale[]).filter((l) => LOCALES[l].published);

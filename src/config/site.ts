/**
 * Central site configuration. Edit here rather than in templates.
 * Anything that names a person, an address or an organisation must be
 * confirmed before it is set (see GOVERNANCE.md).
 */
export const SITE = {
  name: 'Algeria Earth Observatory',
  shortName: 'AEO',
  tagline: 'Open Earth Data for Algeria',
  url: 'https://algeria-earth-observatory.github.io',
  description:
    'An open, community-driven scientific initiative for discovering, visualising, documenting and accessing Earth observation and environmental data for Algeria.',
  /** Development phase shown in the footer and About page. */
  phase: 'Initial development phase',
  github: {
    org: 'algeria-earth-observatory',
    orgUrl: 'https://github.com/algeria-earth-observatory',
    repo: 'algeria-earth-observatory.github.io',
    repoUrl: 'https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io',
  },
  /**
   * Founding maintainer. Shown on About/Community/Governance only.
   * Set to null to publish without a named person.
   */
  founder: { name: 'Walid Ouaret', github: 'ouaretw' } as { name: string; github: string } | null,
  /**
   * Private contact address. Leave null until an organisational mailbox exists;
   * the Contact page then routes people to GitHub and explains the gap.
   */
  contactEmail: null as string | null,
} as const;

export const NAV = [
  { href: '/map/', label: 'Explore' },
  { href: '/data/', label: 'Data' },
  { href: '/drought/', label: 'Drought' },
  { href: '/water/', label: 'Water' },
  { href: '/climate/', label: 'Climate' },
  { href: '/science/', label: 'Science' },
  { href: '/contribute/', label: 'Contribute' },
  { href: '/about/', label: 'About' },
] as const;

export const issueUrl = (template?: string, title?: string, body?: string) => {
  const u = new URL(`${SITE.github.repoUrl}/issues/new`);
  if (template) u.searchParams.set('template', template);
  if (title) u.searchParams.set('title', title);
  if (body) u.searchParams.set('body', body);
  return u.toString();
};

export const editUrl = (path: string) => `${SITE.github.repoUrl}/edit/main/${path}`;

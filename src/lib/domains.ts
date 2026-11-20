export const DOMAIN_IDS = [
  'agriculture',
  'climate-drought',
  'water',
  'land-ecosystems',
  'hazards',
  'human-change',
  'reference',
] as const;
export type DomainId = (typeof DOMAIN_IDS)[number];

export interface Domain {
  id: DomainId;
  title: string;
  short: string;
  summary: string;
  topics: string[];
  /** Development priority shown on the domain card. */
  priority?: 'initial priority' | 'future expansion';
  /** Cross-cutting data (boundaries, base imagery) not shown as a domain card. */
  crossCutting?: boolean;
}

export const DOMAINS: Domain[] = [
  {
    id: 'agriculture',
    title: 'Agriculture & Cropland',
    short: 'Agriculture',
    priority: 'initial priority',
    summary:
      'Cropland extent and change, winter cereals, irrigated and rainfed systems, crop condition and agricultural drought in Algeria’s dryland farming systems.',
    topics: [
      'Cropland extent and distribution',
      'Agricultural land-use change',
      'Active cropland and fallow land',
      'Winter cereals',
      'Irrigated and rainfed agriculture',
      'Crop calendars and growing seasons',
      'Vegetation indices and crop condition',
      'Greenhouse agriculture',
      'Crop-type mapping and field reference data',
      'Production and yield statistics',
    ],
  },
  {
    id: 'climate-drought',
    title: 'Climate & Drought',
    short: 'Climate',
    summary:
      'Precipitation, temperature, evapotranspiration, soil moisture and drought indices from monthly to long-term scales, including projections.',
    topics: [
      'Precipitation',
      'Air and land surface temperature',
      'Evapotranspiration',
      'Soil moisture',
      'SPEI and SPI drought indices',
      'Climate anomalies and heatwaves',
      'Historical trends',
      'Climate projections and scenarios',
    ],
  },
  {
    id: 'water',
    title: 'Water Resources',
    short: 'Water',
    summary:
      'Surface water and reservoirs, river basins, wetlands, hydrological drought and irrigation-related water pressure.',
    topics: [
      'Surface water extent',
      'Reservoirs and dams',
      'Groundwater-related datasets',
      'River basins and watersheds',
      'Wetlands',
      'Hydrological drought',
      'Irrigation demand and water-use pressure',
    ],
  },
  {
    id: 'land-ecosystems',
    title: 'Land & Ecosystems',
    short: 'Land',
    summary:
      'Land cover, vegetation dynamics, forests, soils, rangelands, desertification and land degradation.',
    topics: [
      'Land-cover maps',
      'Vegetation dynamics',
      'Forest cover and change',
      'Desertification and land degradation',
      'Soil properties',
      'Rangelands and grazing systems',
      'Terrain and elevation',
    ],
  },
  {
    id: 'hazards',
    title: 'Environmental Hazards',
    short: 'Hazards',
    summary:
      'Wildfires and burned area, floods, extreme heat, dust and sandstorms, air pollution and compound hazards.',
    topics: [
      'Wildfires and burned areas',
      'Floods',
      'Extreme heat',
      'Dust and sandstorms',
      'Air pollution',
      'Compound hazards',
    ],
  },
  {
    id: 'human-change',
    title: 'Human & Environmental Change',
    short: 'Human',
    priority: 'future expansion',
    summary:
      'Settlements, population, infrastructure and human pressure on ecosystems — a future expansion domain.',
    topics: [
      'Urban expansion',
      'Population and settlement distribution',
      'Infrastructure and land transformation',
      'Human pressure on ecosystems',
      'Environmental exposure and vulnerability',
    ],
  },
  {
    id: 'reference',
    title: 'Reference data',
    short: 'Reference',
    crossCutting: true,
    summary: 'Boundaries, base imagery and elevation that support work in every domain.',
    topics: ['Administrative boundaries', 'Satellite imagery', 'Elevation'],
  },
];

export const THEMATIC_DOMAINS = DOMAINS.filter((d) => !d.crossCutting);

export const domainById = (id: string) => DOMAINS.find((d) => d.id === id);

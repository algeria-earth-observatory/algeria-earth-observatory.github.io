export const DOMAIN_IDS = [
  'agriculture',
  'climate-drought',
  'water',
  'soil',
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
  /** One of the five main environmental domains shown on the homepage and in Explore. */
  primary?: boolean;
}

export const DOMAINS: Domain[] = [
  {
    id: 'agriculture',
    title: 'Agriculture & Land Use',
    short: 'Agriculture',
    primary: true,
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
    primary: true,
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
    primary: true,
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
    id: 'soil',
    title: 'Soil & Land Properties',
    short: 'Soil',
    primary: true,
    summary:
      'Soil organic carbon and carbon stocks, texture, pH, bulk density, nutrients, coarse fragments, salinity and water-holding properties, from soil maps, model predictions and profile measurements.',
    topics: [
      'Soil organic carbon and stocks',
      'Texture (sand, silt, clay)',
      'pH, cation exchange capacity, nitrogen',
      'Bulk density and coarse fragments',
      'Soil depth and water-holding properties',
      'Salinity',
      'Soil profile observations',
      'Terrain and elevation',
    ],
  },
  {
    id: 'land-ecosystems',
    title: 'Vegetation & Ecosystems',
    short: 'Vegetation',
    primary: true,
    summary:
      'Land cover, vegetation greenness and productivity, forests, rangelands, wildfire, desertification and land degradation.',
    topics: [
      'Land-cover maps',
      'Vegetation indices (NDVI, EVI) and productivity',
      'Forest cover and change',
      'Wildfire and burned area',
      'Desertification and land degradation',
      'Rangelands and grazing systems',
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
export const PRIMARY_DOMAINS = DOMAINS.filter((d) => d.primary);

export const domainById = (id: string) => DOMAINS.find((d) => d.id === id);

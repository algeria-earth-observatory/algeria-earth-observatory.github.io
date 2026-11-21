---
title: "Tutorial (Python): soil organic carbon of a wilaya with SoilGrids"
description: Read the SoilGrids 2.0 soil organic carbon map for one wilaya directly from ISRIC, compute its mean in the equal-area projection, and compare it with the AEO soil statistics.
section: Tutorials
order: 94
updated: 2026-11-21
---

## Scientific objective

Compute the mean predicted **soil organic carbon** (SOC) concentration at 0–5 cm for one wilaya from the SoilGrids 2.0 map. Then check the AEO soil statistics, and read the result with its uncertainty.

## Data sources

- **ISRIC SoilGrids 2.0**, 1 km aggregate of the 250 m predictions. File: `soc_0-5cm_mean_1000.tif`, read over the network (only the window over the wilaya, about 1–2 MB). Licence CC BY 4.0; reference Poggio et al. (2021), doi:10.5194/soil-7-217-2021.
- **AEO wilaya boundaries** ([record](/data/aeo-dza-admin-boundaries/)).
- **AEO soil statistics** ([record](/data/aeo-dza-soil-soilgrids/)), used for the comparison.

## Dependencies

```bash
pip install geopandas rasterio numpy pandas pyarrow
```

## Code

The script is [`scripts/tutorials/soil_wilaya.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/tutorials/soil_wilaya.py). Its key steps:

```python
with rasterio.open("/vsicurl/https://files.isric.org/soilgrids/latest/data_aggregated/1000m/soc/soc_0-5cm_mean_1000.tif") as ds:
    wi = wilaya.to_crs(ds.crs)            # Interrupted Goode Homolosine: equal-area
    window = from_bounds(*wi.total_bounds, ds.transform).round_offsets().round_lengths()
    a = ds.read(1, window=window).astype(float)
    inside = geometry_mask(wi.geometry, out_shape=a.shape, transform=ds.window_transform(window), invert=True)
soc = a[inside] / 10                      # dg/kg -> g/kg (ISRIC conversion factor)
mean = np.nanmean(soc)                    # equal-area pixels: plain mean = area-weighted mean
```

## Output (run on 21 November 2026, wilaya of Sétif)

```text
Sétif (wilaya 19): 6665 pixels of 1 km²
Soil organic carbon 0–5 cm, mean of predictions: 31.10 g/kg (AEO table: 31.09 g/kg)
Average pixel 5–95 % prediction range (AEO table): 4.57–87.18 g/kg
```

## Interpretation

- **The two means agree to 0.01 g/kg.** The small gap comes from pixels on the wilaya edge.
- **The prediction range is very wide.** For a typical 1 km pixel the model's 90 % interval spans about 5 to 87 g/kg. The mean is a model estimate, not a measured value, and differences between nearby wilayas may not be meaningful.
- **This is a concentration, not a stock.** For carbon stocks (t/ha), use the SoilGrids organic carbon stock layer (`ocs`, 0–30 cm), also summarised by AEO.

## Limitations

- **Few profiles.** SoilGrids is trained on few soil profiles in Algeria; dryland soils are often poorly predicted.
- **1 km aggregate.** The 1 km map averages the 250 m predictions, so small soil patches are smoothed.
- **Not soil samples.** For field measurements, see soil profile databases such as WoSIS in the [Data catalog](/data/?domain=soil).

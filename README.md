# plot-indices

Downloads Sentinel-2 imagery for a set of cadastral parcels and computes vegetation/water spectral indices (NDVI, GNDVI, NDWI, NDMI), rendering each as a raster figure.

## How it works

1. Parcel geometries are fetched from the Spanish Catastro WFS service using reference cadastral codes (`REFCATS`).
2. The parcel's bounding box is used to query the [Copernicus Data Space](https://dataspace.copernicus.eu/) OData API for the most recent matching Sentinel-2 L2A product.
3. Temporary S3 credentials are requested from Copernicus and the required bands (`B02`-`B12`) are downloaded to `downloads/`.
4. Each band is clipped to the parcel geometry and reprojected to UTM.
5. Indices are computed and saved as PNGs under `figures/`.

## Setup

Requires Python >= 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a `.env` file with your [Copernicus Data Space](https://dataspace.copernicus.eu/) credentials:

```
username=your-email@example.com
password=your-password
```

## Usage

```bash
uv run main.py
```

Output figures are written to `figures/` (polygon previews) and `figures/rasters/` (index maps). Downloaded Sentinel-2 products are cached under `downloads/`.

## Project structure

- `main.py` — parcel lookup, product download, and index computation
- `viz.py` — plotting helpers for polygons and rasters
- `tokengen.py` — Copernicus authentication token generation

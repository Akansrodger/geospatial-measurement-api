# Geospatial File Measurement API

A backend service built with **FastAPI**. You upload a map file (a zipped **Shapefile** or a **KML**), and it returns the **area** of polygons and the **length** of lines, measured in metres.

## Setup

You need Python 3.11 or newer.

```bash
git clone <your-repo-url>
cd geospatial-measurement-api

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

python -m pip install -r requirements.txt
python -m uvicorn app.main:create_app --factory --reload
```

Then open **http://127.0.0.1:8000/docs**. This page lets you try every endpoint in your browser.
A sample file is included: `samples/sample.kml`.

To run the tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

## API

| Endpoint | What it does |
|---|---|
| `POST /api/files/` | Upload a `.kml` or a `.zip` containing a Shapefile |
| `GET /api/files/{id}/` | Get information about an uploaded file |
| `GET /api/files/{id}/measurements/` | Get the area or length of every feature |
| `GET /api/files/{id}/features/` | Get full features (geometry, CRS, properties) |
| `GET /health` | Check the service is running |

**Example: upload a file**

```bash
curl -F "file=@samples/sample.kml" http://127.0.0.1:8000/api/files/
```

```json
{
  "id": "9f2c1b7e4a0d4c0e8f3a6b1d2c3e4f50",
  "filename": "sample.kml",
  "feature_count": 5,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

**Example: get measurements** (`GET /api/files/9f2c.../measurements/`, shortened)

```json
{
  "features": [
    {
      "index": 0,
      "geometry_type": "Polygon",
      "measurement": { "status": "MEASURED", "area_sq_m": 1181000.0, "measurement_crs": "EPSG:32631" }
    },
    {
      "index": 2,
      "geometry_type": "Point",
      "measurement": { "status": "NOT_REQUIRED" }
    }
  ]
}
```

*The numbers are examples. Upload the sample file to see the real values.*

**Errors:** `415` wrong file type, `413` file too large, `422` the file is broken or has no CRS, `404` unknown id.

## Architecture

```
app/
  main.py              starts the app
  api/files.py         the endpoints
  services/
    processor.py       runs the steps in order
    parsers/           readers for KML and Shapefile
    crs.py, utm.py     coordinate system handling
    measurements.py    calculates area and length
  repository.py        saves results in a SQLite database
tests/                 automated tests
```

**File-processing flow**
1. The file is uploaded and its type is checked.
2. A reader extracts every feature: its index, geometry type, geometry, CRS and properties.
3. Each feature is measured.
4. The results are saved to the database and can be fetched later.

**Measurement flow**
- Polygons get an area, and lines get a length.
- Points need no measurement.
- Shapes that can't be measured get a clear status such as `UNSUPPORTED` instead of crashing the app.

**CRS handling**
Latitude and longitude are measured in degrees, and a degree is not a fixed distance, so measuring in degrees gives wrong answers. Before measuring, every shape is converted to a **UTM zone**, a flat map projection in metres that fits the shape's location. The zone used is returned in `measurement_crs`.

## Design Decisions

- **FastAPI** instead of Django: simpler for a small service, and it generates the `/docs` page automatically.
- **UTM projection chosen per feature**: accurate and widely used. I also considered one projection per file (less accurate for large files) and geodesic measurement (the brief asks for a projected CRS).
- **Always re-project, even if the file is already projected**: some projections, like Web Mercator, distort area badly.
- **Pure-Python readers (`pyshp`, `lxml`)**: no GDAL to install, so setup is easy.
- **SQLite database**: no setup needed, and it can be swapped for PostgreSQL later.
- **One bad feature never breaks the whole file**: it is reported with a status and the rest are still measured.
- **Shapefile without a `.prj` is rejected**: guessing the CRS would silently give wrong results. The `crs` form field lets users provide it.

## Learnings

- Degrees are not a unit of area. The same 1° box is far smaller at 60°N than at the equator.
- A "projected" map is not always good for measuring. Web Mercator is the classic trap.
- Real files are messy, so planning for missing or odd data early made the code more reliable.
- Uploaded files should be treated as untrusted: I added size limits and safe XML parsing.

## Future Scope

- Process large files in the background.
- Move to PostgreSQL with PostGIS for spatial queries.
- Support more formats: KMZ, GeoJSON, GeoPackage.
- Add perimeter and a geodesic measurement option.
- Add authentication and file deletion.

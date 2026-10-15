# Weather-Aware Truck Routing

A full-stack React + Django implementation of the Spotter Full Stack Developer assessment. The application compares route alternatives using weather at the truck's estimated arrival time, applies the supplied wind/rain/snow and load rules, and recommends a route using the exact priority order from the brief.

## What is implemented

- Origin, destination, departure date/time and load weight inputs.
- 10 / 25 / 50 mile checkpoint sampling.
- Up to 3 alternatives from the routing provider.
- Geocoding with OpenStreetMap Nominatim.
- Routing with OSRM by default; optional Mapbox adapter via environment variable.
- Weather forecasts with Open-Meteo.
- ETA-aware weather lookup at every checkpoint.
- Exact risk thresholds from the assessment:
  - Wind: <25 Low, 25–34 Moderate, 35–44 High, 45–54 Severe, ≥55 No Travel.
  - Rain: <0.10 Low, 0.10–0.25 Moderate, 0.25–0.50 High, 0.50–1.00 Severe, >1.00 No Travel.
  - Snow: <0.5 Low, 0.5–1.0 Moderate, 1.0–2.0 High, 2.0–3.0 Severe, >3.0 No Travel.
- Load rules:
  - ≥55 mph: No Travel for any load.
  - 45–54 mph + >30,000 lb: No Travel.
  - 35–44 mph + >40,000 lb: Severe.
- Recommendation priority:
  1. Fewest Severe / No-Travel miles
  2. Fewest High miles
  3. Lowest average risk
  4. Shortest travel time
- Interactive Leaflet map with route alternatives, checkpoint markers and a 0–48 hour heatmap slider.
- Responsive, professional dashboard UI.
- Docker Compose and Render deployment configuration.

The assessment asks for a GitHub repository, hosted application and a 5–10 minute Loom walkthrough. The source is deployment-ready, but publishing to your GitHub/hosting accounts and recording the walkthrough require your credentials/accounts.

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
python manage.py runserver 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Vite proxies `/api` to Django during local development.

## API notes

The default stack uses public, keyless endpoints. Respect the providers' acceptable-use/rate-limit policies. For production, an API-key-backed provider such as Mapbox can be selected by setting:

```env
ROUTING_PROVIDER=mapbox
MAPBOX_ACCESS_TOKEN=your-token
```

If a provider returns fewer than three native alternatives, the backend asks the same routing API for two small via-waypoint variants. These are real routed road paths, not cloned polylines, so the assessment still receives three independently scored candidates whenever the provider can route them.

## Production deployment

### Render

`render.yaml` defines the Django API and frontend static site. Deploy the repository in Render, then set `VITE_API_BASE_URL` on the frontend service to the API service's public URL.

### Vercel + Render

Build the frontend with `npm run build` and set `VITE_API_BASE_URL` to the deployed Django origin. Deploy the `backend` folder separately to Render/Fly.io/Railway or another Python host.

## Assessment walkthrough

Suggested 6-minute Loom flow:

1. Show the planner inputs and enter a real corridor.
2. Run a 25-mile checkpoint plan.
3. Explain the recommendation and route priority order.
4. Click each route and inspect severe/high miles and duration.
5. Toggle checkpoints and move the 0–48h weather slider.
6. Open the checkpoint table and explain that weather is evaluated at estimated arrival time.
7. Change the load from 30,000 to 45,000 lb to demonstrate the wind load rule.

## Architecture

```text
React/Vite
  │
  ├── Leaflet map + heat layer
  └── POST /api/plan/
          │
          ▼
Django API
  ├── Nominatim geocoding
  ├── OSRM / Mapbox routing
  ├── Open-Meteo weather
  ├── checkpoint interpolation + ETA
  ├── risk/load rules
  └── lexicographic recommendation
```

## Important implementation decision

Weather is sampled on the route geometry rather than only at origin/destination. Each checkpoint's forecast is selected using the truck's interpolated ETA, which directly addresses the core requirement in the assessment.

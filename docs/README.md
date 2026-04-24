# ✈ AvionDash Docker

> **Aviation Operations Monitoring Platform — Containerised Datadog Demo**

A fully containerised, three-tier aviation operations dashboard purpose-built to validate and demonstrate Datadog observability across a realistic multi-service Docker environment. Every tier produces genuine APM traces, structured logs, and infrastructure metrics. The chaos engine lets you inject specific faults and immediately observe the resulting Datadog signals.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        Browser / RUM                           │
└──────────────────────────────┬─────────────────────────────────┘
                               │ HTTP :80
         ┌─────────────────────▼──────────────────────┐
         │          WEB TIER — Nginx 1.25              │
         │  • Serves static SPA (HTML / CSS / JS)      │
         │  • Reverse-proxies /api/* → App tier         │
         │  • JSON structured access logs               │
         └─────────────────────┬──────────────────────┘
                               │ HTTP :8000  [aviondash-backend]
         ┌─────────────────────▼──────────────────────┐
         │       APPLICATION TIER — FastAPI            │
         │  • REST API: auth, flights, aircraft,       │
         │    airports, dashboard, chaos               │
         │  • JWT authentication (bcrypt passwords)    │
         │  • Fault injection middleware               │
         │  • ddtrace APM auto-instrumentation         │
         └─────────────────────┬──────────────────────┘
                               │ MySQL :3306  [aviondash-backend]
         ┌─────────────────────▼──────────────────────┐
         │         DATABASE TIER — MySQL 8.0           │
         │  • 25 airports, 15 aircraft, 25 flights     │
         │  • 4 demo users (hashed via bcrypt)         │
         │  • Auto-seeded from db/init/01_seed.sql     │
         └────────────────────────────────────────────┘
```

### Datadog Integration (optional)

The Datadog Agent block is **commented out** in `docker-compose.yml`. To enable it:

1. Set `DD_API_KEY` in your `.env` file
2. Uncomment the `datadog-agent` block in `docker-compose.yml`
3. Set `DD_TRACE_ENABLED=true` in the `app` service environment
4. Run `docker compose up -d`

See [`docs/DATADOG_SETUP.md`](docs/DATADOG_SETUP.md) for full configuration.

---

## Quick Start

### Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Docker Engine | 24.0+ |
| Docker Compose | v2.20+ |
| RAM | 4 GB available |
| Disk | 5 GB free |

### 1 — Clone and configure

```bash
git clone https://github.com/your-org/aviondash-docker.git
cd aviondash-docker
cp .env.example .env
```

### 2 — Start all services

```bash
docker compose up -d --build
```

First run: Docker pulls images and builds the Python app container (~3 min). The MySQL seed script runs automatically on first start.

### 3 — Open the dashboard

```
http://localhost
```

### 4 — Log in

| Username | Password | Role |
|----------|----------|------|
| `admin` | `aviondash123` | Admin — full chaos control access |
| `operator` | `aviondash123` | Operator — read + view |
| `viewer` | `aviondash123` | Read-only |
| `demo` | `aviondash123` | Admin (demo account) |

> Passwords are hashed fresh by the application on first startup using bcrypt — they are never stored as plain text in SQL.

---

## Service Reference

| Service | Container | Port | Image |
|---------|-----------|------|-------|
| Web | `aviondash-web` | 80 | `nginx:1.25-alpine` |
| App | `aviondash-app` | 8000 | Custom (Python 3.12 slim) |
| Database | `aviondash-db` | 3306 | `mysql:8.0` |

---

## Dashboard Pages

### ◉ Dashboard
Live KPI summary — total flights, en-route count, delayed, cancelled, fleet size, on-time rate. Includes an interactive world flight map showing airport locations and live flight positions, plus system health metrics and busiest departure airports chart.

### ✈ Flights
Paginated flight table with status filter. Shows flight number, route, status badge, departure time, gate, altitude, and delay in minutes. All data pulled live from the FastAPI → MySQL stack.

### ⚙ Aircraft
Fleet registry table. Filter by status (active / maintenance / grounded / retired). Shows tail number, model, manufacturer, capacity, range, engine type, year, and cumulative flight hours.

### 🏛 Airports
Airport directory. 25 international airports with IATA/ICAO codes, city, country, coordinates, elevation, and runway count.

### ⚡ Chaos Control
Inject faults across the application and container tiers. Each fault card shows:
- What the fault does technically
- The exact Datadog signal / monitor it triggers
- A toggle to enable/disable instantly
- The current active/inactive state

Admin role required. See [`docs/FAULT_SCENARIOS.md`](docs/FAULT_SCENARIOS.md) for full detail on all 14 faults.

---

## API Reference

Interactive Swagger docs: `http://localhost/api/docs`

### Authentication

```bash
# Get a JWT token
curl -X POST http://localhost/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=aviondash123"

# Store token
TOKEN=$(curl -s -X POST http://localhost/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=aviondash123" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/token` | Login — returns JWT |
| `GET` | `/api/auth/me` | Current user info |
| `GET` | `/api/dashboard/summary` | KPIs + system health |
| `GET` | `/api/flights/` | List flights (filter: `?status=en_route`) |
| `GET` | `/api/flights/stats` | Flight counts by status |
| `GET` | `/api/aircraft/` | List aircraft (filter: `?status=active`) |
| `GET` | `/api/airports/` | List airports |
| `GET` | `/api/chaos/status` | Current fault state |
| `GET` | `/api/chaos/catalog` | All available faults with descriptions |
| `POST` | `/api/chaos/{fault}/toggle` | Enable/disable a fault `{"enabled": true}` |
| `POST` | `/api/chaos/reset-all` | Clear all active faults |
| `GET` | `/health` | App health check |
| `GET` | `/health/db` | Database connectivity check |

---

## Project Structure

```
aviondash-docker/
├── docker-compose.yml          # Three-tier orchestration
├── .env.example                # Environment template
├── README.md
│
├── nginx/
│   ├── conf/
│   │   ├── nginx.conf          # Main Nginx config (JSON logging)
│   │   └── aviondash.conf      # Virtual host + /api/ proxy rules
│   └── html/
│       ├── index.html          # Single-page app shell
│       └── static/
│           ├── css/app.css     # Glass-cockpit dark theme
│           ├── js/app.js       # SPA controller + chaos UI
│           └── img/world.svg   # Flight map world background
│
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # FastAPI entry point + fault middleware
│   ├── database.py             # SQLAlchemy engine + session
│   ├── init_db.py              # Demo user seeding (bcrypt, on startup)
│   ├── models/
│   │   ├── users.py
│   │   ├── flights.py
│   │   ├── aircraft.py
│   │   └── airports.py
│   └── api/
│       ├── auth.py             # JWT login + token validation
│       ├── flights.py          # Flight CRUD + fault-aware queries
│       ├── aircraft.py
│       ├── airports.py
│       ├── dashboard.py        # Summary KPI aggregation
│       └── chaos.py            # Fault injection engine
│
├── db/
│   └── init/
│       └── 01_seed.sql         # Schema + airport/aircraft/flight data
│
└── docs/
    ├── SETUP.md                # Detailed deployment guide
    ├── FAULT_SCENARIOS.md      # All 14 chaos faults documented
    └── DATADOG_SETUP.md        # Monitor, APM, log, synthetic setup
```

---

## Operational Commands

```bash
# View logs per tier
docker compose logs -f web
docker compose logs -f app
docker compose logs -f db

# Shell into the app container
docker compose exec app bash

# Test app tier directly (bypassing Nginx)
curl http://localhost:8000/health
curl http://localhost:8000/health/db

# Test through Nginx
curl http://localhost/health

# Restart a single tier after code change
docker compose restart app

# Rebuild app image after source change
docker compose up -d --build app

# Stop everything (keeps data volumes)
docker compose down

# Full reset including all data
docker compose down -v
docker compose up -d --build
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Login fails — `Incorrect username or password` | Users not seeded yet | Check `docker compose logs app` for `Demo users ready` message |
| 404 on `/api/*` | App container not healthy | `docker compose ps` — wait for `(healthy)`, then retry |
| 502 Bad Gateway | App crashed or starting | `docker compose logs app --tail 50` |
| Map shows no geography | Browser blocked `/static/img/world.svg` | Check browser console, verify Nginx is serving static files |
| DB seed didn't apply | Volume already exists from old run | `docker compose down -v && docker compose up -d --build` |
| Port 80 in use | Another service on port 80 | Change `"80:80"` to `"8080:80"` in `docker-compose.yml` |

---

## Datadog Integration Summary

When the agent is enabled (see `docs/DATADOG_SETUP.md`):

- **APM**: Distributed traces across Nginx → FastAPI → MySQL via `ddtrace`
- **Logs**: All three containers emit structured JSON logs collected by the agent
- **Metrics**: Container CPU, memory, network, disk via the process agent
- **Synthetics**: `/health` endpoint monitored every minute
- **Monitors**: 16 pre-defined monitors covering all fault scenarios

The chaos engine is designed so each of the 14 faults maps directly to one or more specific Datadog monitor types — see `docs/FAULT_SCENARIOS.md`.

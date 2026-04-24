# AvionDash Docker

Three-tier containerised aviation operations dashboard for Datadog demos.

## Stack
- **Web**: Nginx 1.25 (Alpine) — SPA + reverse proxy
- **App**: FastAPI (Python 3.12) — REST API + JWT auth + chaos engine
- **DB**: MySQL 8.0 — auto-seeded schema

## Quick Start
```bash
cp .env.example .env          # optionally add DD_API_KEY
docker compose up -d --build
open http://localhost
```

**Login**: `admin / aviondash123`

## Troubleshooting
```bash
docker compose ps                    # check all services healthy
docker compose logs app --tail 50    # check app startup
curl http://localhost:8000/health    # test app directly (bypass nginx)
curl http://localhost/health         # test through nginx
```

See `docs/` for SETUP.md, FAULT_SCENARIOS.md, and DATADOG_SETUP.md.

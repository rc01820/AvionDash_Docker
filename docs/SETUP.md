# AvionDash Docker — Setup Guide

Step-by-step deployment reference for all environments.

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Linux, macOS, Windows (WSL2) | Ubuntu 22.04+ or RHEL 9 |
| Docker Engine | 24.0 | 25.0+ |
| Docker Compose | v2.20 | v2.24+ |
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 5 GB free | 20 GB free |
| Ports | 80, 3306, 8000 free | — |

---

## Install Docker

**Ubuntu / Debian**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version  # should show v2.x
```

**RHEL 9 / Rocky / AlmaLinux**
```bash
sudo dnf install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

**macOS / Windows**
Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). Ensure at least 4 GB RAM is allocated to Docker in Settings.

---

## Deployment

### 1. Unzip the project

```bash
unzip aviondash-docker.zip
cd avd
```

### 2. Configure environment

```bash
cp .env.example .env
```

Default `.env` works without changes. Only edit if you need to:
- Change MySQL credentials (not required for a local demo)
- Add a Datadog API key (optional — see `docs/DATADOG_SETUP.md`)
- Change the app secret key for production use

```env
# .env
MYSQL_ROOT_PASSWORD=aviondash_root
MYSQL_DATABASE=aviondash
MYSQL_USER=aviondash
MYSQL_PASSWORD=aviondash_pass
SECRET_KEY=aviondash-secret-key-change-in-prod

# Datadog (leave blank to run without the agent)
DD_API_KEY=
DD_SITE=datadoghq.com
```

### 3. Build and start

```bash
docker compose up -d --build
```

**What happens on first start:**

1. Docker pulls `mysql:8.0` and `nginx:1.25-alpine` (~400 MB total)
2. Docker builds the Python app image (~800 MB with deps)
3. MySQL starts and runs `db/init/01_seed.sql` (airports, aircraft, flights)
4. FastAPI app starts and runs `init_db.py` (creates demo users with bcrypt hashes)
5. Nginx starts and waits for the app health check to pass
6. All three services show as healthy

**Timeline:** First build takes 3–5 minutes. Subsequent starts take ~30 seconds.

### 4. Verify deployment

```bash
# All three services should show (healthy)
docker compose ps

# Test app tier directly
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"aviondash-app"}

# Test database connectivity
curl http://localhost:8000/health/db
# Expected: {"status":"ok","database":"connected"}

# Test through Nginx
curl http://localhost/health
# Expected: {"status":"ok","service":"aviondash-app"}

# Open dashboard
open http://localhost     # macOS
xdg-open http://localhost # Linux
```

### 5. Log in

Open `http://localhost` and log in with:
- **Username:** `admin`
- **Password:** `aviondash123`

---

## Startup Sequence Detail

The services have strict health check dependencies:

```
MySQL starts
  └─ Waits for: mysqladmin ping responds (up to 100s)
       └─ FastAPI app starts
            └─ Creates tables (SQLAlchemy create_all)
            └─ Seeds demo users (init_db.py via bcrypt)
            └─ Waits for: /health returns 200 (up to 125s)
                 └─ Nginx starts
                      └─ Serves SPA + proxies /api/*
```

If any tier fails, check its logs:
```bash
docker compose logs db  --tail 50
docker compose logs app --tail 50
docker compose logs web --tail 50
```

---

## Changing Ports

If ports 80 or 3306 are in use on your host:

```yaml
# docker-compose.yml — web service
ports:
  - "8080:80"    # Use http://localhost:8080 instead

# docker-compose.yml — db service
ports:
  - "3307:3306"  # MySQL available on 3307 from host
```

The app container communicates with MySQL over the internal Docker network (`aviondash-backend`) and is unaffected by host port changes.

---

## Data Management

### Reset all data (full clean slate)

```bash
docker compose down -v           # removes containers AND volumes
docker compose up -d --build     # rebuilds everything fresh
```

### Reset only the database

```bash
docker compose stop db
docker volume rm aviondash-db-data
docker compose up -d db
# Wait ~30s for MySQL to reinitialise and seed
docker compose up -d app         # restart app to reconnect
```

### Access MySQL directly

```bash
# From host (requires mysql client)
mysql -h 127.0.0.1 -P 3306 -u aviondash -paviondash_pass aviondash

# From inside the container
docker compose exec db mysql -u aviondash -paviondash_pass aviondash

# Useful queries
SELECT flight_number, origin_iata, destination_iata, status FROM flights LIMIT 10;
SELECT username, role, last_login FROM users;
```

### Export a database snapshot

```bash
docker compose exec db \
  mysqldump -u aviondash -paviondash_pass aviondash \
  > aviondash_backup_$(date +%Y%m%d).sql
```

---

## Updating After Code Changes

```bash
# Rebuild only the app container (fastest)
docker compose up -d --build app

# Full rebuild of all images
docker compose up -d --build

# Apply a new nginx config without rebuild
docker compose exec web nginx -s reload
```

---

## Running Without Nginx (API-only)

If you only need the API tier for testing:

```bash
docker compose up -d db app
# App available directly at http://localhost:8000
# Swagger UI at http://localhost:8000/api/docs
```

---

## Troubleshooting

### App container keeps restarting

```bash
docker compose logs app --tail 100
```

Common causes:
- MySQL not ready yet → wait 30s and run `docker compose restart app`
- Python import error → check the log for `ModuleNotFoundError` or `ImportError`
- Port 8000 in use on host → change the port mapping

### Users can't log in

```bash
docker compose logs app | grep "Demo users ready"
```

If this line doesn't appear, the `init_db.py` script failed. Check:
```bash
docker compose logs app | grep -i "error\|init_db"
```

If the database volume is from a previous run that had a different schema, do a full reset:
```bash
docker compose down -v && docker compose up -d --build
```

### 502 Bad Gateway on http://localhost

The Nginx web tier is up but the app tier is not healthy yet.

```bash
docker compose ps          # is aviondash-app showing (healthy)?
curl http://localhost:8000/health   # is the app directly reachable?
```

### Static files not loading (CSS/JS missing)

```bash
docker compose exec web ls /usr/share/nginx/html/static/css/
docker compose exec web ls /usr/share/nginx/html/static/js/
```

If empty, the volume mount in docker-compose.yml isn't pointing to the right path. Verify `./nginx/html` exists in the project directory.

### Map shows no world geography

The flight map background is served from `/static/img/world.svg`. Check:
```bash
curl http://localhost/static/img/world.svg | head -5
# Should return SVG XML starting with <svg
```

If 404: verify `nginx/html/static/img/world.svg` exists in the project.

### MySQL seed didn't run

MySQL only runs scripts in `/docker-entrypoint-initdb.d/` on a **fresh volume**. If you already have a `aviondash-db-data` volume from a previous run, the seed will not re-run.

```bash
# Check if the volume exists
docker volume ls | grep aviondash

# Full reset
docker compose down -v
docker compose up -d --build
```

---

## Production Considerations

This project is designed as a **demo/lab environment**, not for production. If adapting it:

1. **Change all passwords** in `.env` before exposing to any network
2. **Set a strong `SECRET_KEY`** — JWT tokens are signed with this
3. **Add TLS** — mount certs in the Nginx container and add SSL listener
4. **Remove the Chaos Control page** — or protect it behind network-level access controls
5. **Set memory limits** on the app container to bound the memory leak fault
6. **Use secrets management** instead of `.env` files for credentials

# Server Deployment Status

## Server Information

- **Hostname**: cc-vis.rz.uni-mannheim.de
- **IP Address**: 134.155.106.59
- **SSH Port**: 1907
- **OS**: Ubuntu 24.04 LTS (Linux 6.8.0-101-generic x86_64)
- **SSH Login**: `ssh -p 1907 ccvis@134.155.106.59`

## What's Currently Running on the Server

| Service | Status | Container Name | Port |
|---------|--------|----------------|------|
| FastAPI Backend | ✅ Running | `provibackend` | 1234 → 80 |
| MongoDB | ✅ Running | `mongo` | 27017 |
| Redis | ✅ Running | `redis` | 6379 |
| Nginx | ❌ Not running | `nginx` | 80, 443 |
| Next.js Frontend | ✅ Running | `provifrontend` | 22222 → 3000 |

Data volumes are mounted at `/home/ccvis/data/` (mongo, redis, provibackend).

## Why Frontend and Backend Are Not Connected

The frontend code has all API URLs **hardcoded** to the previous production server:

```
https://pm-vis.uni-mannheim.de/api/...
```

This means the frontend sends all requests to the old server, not to our backend. This needs to be changed to point to our own server once the domain and SSL are set up.

## Why Nginx and HTTPS Are Not Working

Nginx requires an SSL certificate to start. We attempted to obtain one via Let's Encrypt (Certbot), but **ports 80 and 443 are blocked by the university firewall**. We have requested the university IT department (RZ) to open these ports. Once they do:

1. Run `sudo certbot certonly --standalone -d cc-vis.rz.uni-mannheim.de` to get SSL certificate
2. Rebuild and restart: `docker compose up -d` (in `provibackend/`)
3. Nginx will start, and the app will be accessible via `https://cc-vis.rz.uni-mannheim.de`
4. Update all frontend API URLs from `pm-vis.uni-mannheim.de` to `cc-vis.rz.uni-mannheim.de`

## How to Test Right Now

### Option 1: SSH Tunnel (Access Server Services from Your Browser)

Since external ports are blocked, use SSH port forwarding:

```bash
ssh -p 1907 -L 8080:localhost:1234 -L 3001:localhost:22222 ccvis@134.155.106.59
```

Then open in your browser:

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8080/api/ |
| Backend Swagger Docs | http://localhost:8080/api/v1/docs |
| Frontend | http://localhost:3001 |

> **Note**: The frontend at `localhost:3001` still sends API requests to `pm-vis.uni-mannheim.de`, not to your local tunnel. So the frontend will NOT show data from our server. Use Swagger or curl to test the backend directly.

### Option 2: Test Backend via curl on the Server

SSH into the server and use curl directly (no CORS issues):

```bash
# Test backend is running
curl http://localhost:1234/api/

# List datasets
curl http://localhost:1234/api/admin/datasets

# Upload a test XES file
curl -X POST http://localhost:1234/api/admin/upload \
  -F "file=@/home/ccvis/Conformance_Experiment_Platform/provibackend/tests/testdata/NoNoise.xes"
```

### Option 3: Run Locally on Your Mac

See the local development setup below — this runs the full stack on your machine, independent of the server.

## Local Development Setup

### Prerequisites

- Python 3.12
- Node.js 18+
- Docker Desktop (for MongoDB and Redis)

### One-Time Setup

```bash
# Add hostname mapping
sudo sh -c 'echo "127.0.0.1 mongo redis" >> /etc/hosts'

# Create .env in provibackend/
# Contents:
#   LOCAL_DATABASE_USERNAME=root
#   LOCAL_DATABASE_PASSWORD=example

# Create docker-compose.override.yml in provibackend/
# (Replaces server paths with Docker-managed volumes for Mac compatibility)

# Create Python virtual environment
cd provibackend
python3 -m venv venv
./venv/bin/pip install -r ProViBackend/requirements.txt
./venv/bin/pip install python-dotenv

# Install frontend dependencies
cd ProViFrontend/provi-frontend
npm install
```

### Start Services (Every Time)

```bash
# 1. Start Docker Desktop app

# 2. Start MongoDB + Redis
cd provibackend
docker compose up mongo redis -d

# 3. Start backend (keep terminal open)
./venv/bin/fastapi dev ProViBackend/app/main.py --port 8000

# 4. Start frontend in a new terminal (keep open)
cd ProViFrontend/provi-frontend
npm run dev
```

- Backend: http://localhost:8000/api/v1/docs
- Frontend: http://localhost:3000

## Remaining TODOs

- [ ] RZ opens ports 80 and 443 on the firewall
- [ ] Obtain SSL certificate via Certbot
- [ ] Nginx starts successfully with SSL
- [ ] Update frontend API URLs from `pm-vis.uni-mannheim.de` to `cc-vis.rz.uni-mannheim.de`
- [ ] Full end-to-end test with frontend connected to our backend

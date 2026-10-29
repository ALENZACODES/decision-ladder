# Deploying the demo URL

**Nebius Serverless AI (recommended for the "runs on Nebius" story).** The `container image` GitHub Action publishes
`ghcr.io/alenzacodes/decision-ladder:latest` on every push. Make the package public once (GitHub → your profile →
Packages → decision-ladder → Package settings → Change visibility). Then:

```bash
NEBIUS_API_KEY=... TAVILY_API_KEY=... SUBNET_ID=... bash deploy/nebius/endpoint.sh   # CPU endpoint, port 8000
NEBIUS_API_KEY=... BOOK=./book.csv bash deploy/nebius/job.sh                          # nightly renewal-book job
```

The endpoint script uses token auth (`--auth token`), as in the Nebius quickstart. Browsers can't send that header,
so for the judges' click-to-open demo link use Render or a VM (below), and show the Nebius endpoint and job in the video.

Devpost requires a **working demo URL**. The judges' link options follow. Either way, the app runs in offline mode until a key is added. Once you add `NEBIUS_API_KEY`, it switches to live Nemotron by itself, with no code change.

## Option A: Render (free, about 10 minutes)

1. Go to render.com → **New → Blueprint** and connect `ALENZACODES/decision-ladder`. Render reads `render.yaml`, which sets up a Docker web service on the free plan with a health check on `/api/health`.
2. When asked for secrets, enter:
   - `NEBIUS_API_KEY`: your Token Factory key. You can leave it blank today, and the site runs in offline demo mode.
   - `TAVILY_API_KEY`: optional.
3. Deploy. The URL looks like `https://decision-ladder-xxxx.onrender.com`. Check `https://…/api/health`: `"mode"` is `"live"` once the key is set.
4. When the key arrives: Render → the service → **Environment** → add `NEBIUS_API_KEY` → **Save, rebuild and deploy**.

Note: a free Render service sleeps after inactivity, so the first request can take about a minute. Open the URL a few minutes before judges are likely to look, and before you record.

## Option B: Nebius AI Cloud VM (strongest "runs on Nebius" story)

1. In the Nebius AI Cloud console, create a small **CPU** VM (no GPU needed; inference runs on Token Factory). Use Ubuntu 22.04 or 24.04 and allow inbound TCP 80.
2. SSH in and run:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io git
   git clone https://github.com/ALENZACODES/decision-ladder && cd decision-ladder
   sudo docker build -t decision-ladder .
   sudo docker run -d --name dl --restart unless-stopped -p 80:8000 \
     -e NEBIUS_API_KEY=... -e TAVILY_API_KEY=... -e DL_RATE_PER_MIN=12 decision-ladder
   curl -s localhost/api/health
   ```
3. The demo URL is `http://<public-ip>/`. To change the key later: `sudo docker rm -f dl`, then run the same `docker run` again.

## Protecting your credits

Model-backed endpoints (`/api/ladder`, `/api/intake`, `/api/ask`, `/api/book`) allow `DL_RATE_PER_MIN` requests per minute per IP (default 20; 12 is suggested for a public URL). A full ladder run makes about 2 model calls; a copilot question makes 2–4. At the published Token Factory prices this costs a fraction of a cent per run (the usage strip in the app shows the estimate). Your Token Factory dashboard is the authoritative record.

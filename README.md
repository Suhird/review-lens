# ReviewLens

AI-powered consumer product review intelligence engine. Runs entirely on your local machine — no paid APIs required.

## What it does

Type any product name and ReviewLens automatically:

- Scrapes reviews from Amazon, Reddit, Best Buy, and YouTube
- Runs aspect-based sentiment analysis (build quality, performance, value, etc.)
- Detects fake and incentivized reviews using Isolation Forest ML
- Detects sentiment drift over time with change-point detection
- Clusters reviews into emergent themes with UMAP + HDBSCAN
- Synthesizes a structured report with charts, featured quotes, and a verdict score

> **Note:** The frontend code of this project was majorly AI-generated.

## Prerequisites

- **Docker Desktop** (includes Docker Compose) — [download](https://www.docker.com/products/docker-desktop/)
- **16 GB RAM recommended** (Mistral LLM requires ~8 GB)
- **Git**
- Reddit API credentials (free, 2 minutes to get)
- YouTube Data API key (optional, free)

---

## Quick Start

### Step 1: Clone the repository

```bash
git clone https://github.com/your-username/review-lens.git
cd review-lens
```

### Step 2: Copy the environment file

```bash
cp .env.example .env
```

### Step 3: Fill in your Reddit credentials

Open `.env` and fill in:

```
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
```

See [How to get Reddit credentials](#how-to-get-reddit-api-credentials) below.

### Step 4: Run the initialization script

```bash
chmod +x init.sh
./init.sh
```

This will:
1. Start Ollama
2. Pull the Mistral model (~4 GB, one-time download)
3. Start all services (PostgreSQL, Redis, backend, frontend)

### Step 5: Open your browser

```
http://localhost:3000
```

---

## How to get Reddit API credentials

1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Scroll to the bottom and click **"create another app..."**
3. Fill in:
   - **Name:** ReviewLens
   - **App type:** Select **"script"**
   - **Redirect URI:** `http://localhost:8080`
4. Click **"create app"**
5. Your `client_id` is the string under the app name (e.g., `abc123`)
6. Your `client_secret` is labeled "secret"

Copy both values into your `.env` file.

---

## How to get a YouTube API key (optional)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Navigate to **APIs & Services → Enable APIs**
4. Search for and enable **"YouTube Data API v3"**
5. Go to **APIs & Services → Credentials**
6. Click **"Create Credentials" → "API key"**
7. Copy the API key into `.env` as `YOUTUBE_API_KEY`

If you skip this step, YouTube reviews will not be included but everything else works.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                              │
│                                                                     │
│  ┌──────────┐    ┌─────────────────────────────────────────────┐    │
│  │          │    │              FastAPI Backend                │    │ 
│  │  Next.js │    │                                             │    │
│  │ Frontend │───▶│  POST /api/analyze  →  LangGraph Pipeline   │    │
│  │ :3000    │    │  GET  /api/stream/{id}  →  SSE events       │    │
│  │          │    │  GET  /api/report/{id}  →  Final report     │    │
│  └──────────┘    │                                             │    │
│                  │  ┌─────────────────────────────────────┐    │    │
│                  │  │         LangGraph Pipeline          │    │    │
│                  │  │                                     │    │    │
│                  │  │  enrich_query ──▶ scraper_node      │    │    │
│                  │  │       │              │              │    │    │
│                  │  │       │    ┌─────────┤              │    │    │
│                  │  │       │    │ Amazon  │              │    │    │
│                  │  │       │    │ Reddit  │              │    │    │
│                  │  │       │    │ BestBuy │              │    │    │
│                  │  │       │    │ YouTube │              │    │    │
│                  │  │       │    └────┬────┘              │    │    │
│                  │  │       ▼         ▼                   │    │    │
│                  │  │  analysis_node (ABSA + fake         │    │    │
│                  │  │   detection + drift + clustering)   │    │    │
│                  │  │       │                             │    │    │
│                  │  │       ▼                             │    │    │
│                  │  │  synthesis_node (LLM summary)       │    │    │
│                  │  └─────────────────────────────────────┘    │    │ 
│                  └─────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────────────┐   │
│  │ Ollama   │  │PostgreSQL│  │  Redis                           │   │
│  │ :11434   │  │ :5432    │  │  :6379                           │   │
│  │ (Mistral)│  │ pgvector │  │  Job state + 24hr report cache   │   │
│  └──────────┘  └──────────┘  └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How each agent works

### `enrich_query_node`
Sends the product query to Ollama/Mistral to generate 3–5 search variants and aliases (e.g., "Sony WH-1000XM5" → ["Sony XM5", "Sony noise canceling headphones 2024", ...]).

### `scraper_node`
Runs all four scrapers in parallel via `asyncio.gather`:
- **Amazon**: Playwright headless browser, extracts top 3 products, paginates up to 5 review pages each
- **Reddit**: PRAW API wrapper, searches 5 subreddits, extracts posts + comments
- **Best Buy**: Playwright with requests fallback
- **YouTube**: YouTube Data API v3 (optional, free quota)

### `analysis_node`
Runs four analyses sequentially:
1. **ABSA** — batches of 20 reviews sent to Ollama for aspect-based sentiment
2. **Fake detection** — Isolation Forest on 9 engineered features per review
3. **Drift detection** — PELT change-point detection on monthly sentiment averages
4. **Clustering** — SentenceTransformers embeddings → UMAP → HDBSCAN → LLM theme naming

### `synthesis_node`
Computes the overall score programmatically, then calls Ollama to write the executive summary and who-should-buy/skip bullets.

---

## Known limitations

- **Amazon scraping**: Amazon actively blocks scrapers. If you see CAPTCHA warnings in logs, the pipeline will continue with other sources. Consider using a residential proxy or increasing delays.
- **YouTube**: Optional. Requires a free Google API key. Daily quota is 10,000 units (sufficient for ~50 product searches).
- **Ollama speed**: Analysis time depends heavily on your hardware. On an M2 MacBook, a full analysis takes ~3–8 minutes. On a machine without a GPU it may take 15–30 minutes.
- **Clustering**: Requires at least 10 reviews. Very niche products with few reviews will not have theme clusters.
- **Reddit**: Must have valid Reddit API credentials. Rate-limited to ~60 requests/minute in read-only mode.

---

## Troubleshooting

### "Ollama did not start in time"
```bash
docker logs reviewlens_ollama
# If container is running but not healthy, wait longer:
docker exec reviewlens_ollama ollama pull mistral
```

### "Backend is unhealthy"
```bash
docker logs reviewlens_backend
# Common cause: Ollama not ready. Wait 30-60s after init.sh completes.
```

### Amazon returns CAPTCHA
This is normal. Amazon blocks automated requests. The pipeline will use Reddit and Best Buy data. Consider setting `AMAZON_DELAY_MIN=5` in your `.env`.

### "Reddit credentials not configured"
Make sure `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are set in `.env`. Verify them at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps).

### PostgreSQL connection errors
```bash
docker logs reviewlens_postgres
# Wait for "database system is ready to accept connections"
docker restart reviewlens_backend
```

### Out of memory errors
Mistral requires ~6–8 GB RAM. Close other applications. If you have less than 12 GB RAM total, try switching to a smaller model:
```
OLLAMA_MODEL=llama3.2:1b
```
Then re-run `docker exec reviewlens_ollama ollama pull llama3.2:1b`.

### Reset everything
```bash
docker compose down -v  # removes all volumes including cached data
./init.sh
```

---

## Development

To run backend locally (outside Docker):

```bash
cd backend
uv pip install -e .
playwright install chromium
uvicorn api.main:app --reload
```

To run frontend locally:

```bash
cd frontend
npm install
npm run dev
```

---

## Switching models

Set `OLLAMA_MODEL` in `.env` to any Ollama-supported model:

```
OLLAMA_MODEL=llama3.2      # faster, less capable
OLLAMA_MODEL=mixtral       # slower, more capable
OLLAMA_MODEL=mistral       # default, good balance
```

Pull the model first:
```bash
docker exec reviewlens_ollama ollama pull llama3.2
```

---

## Future Improvements

### Scraping: proxy & API options

Amazon and Best Buy actively block headless browsers. If you need more reliable or higher-volume scraping, here are your options:

#### Paid proxy services

| Service | Pricing | Notes |
|---------|---------|-------|
| **ScraperAPI** | Free tier (1,000 req/mo), $29/mo for 250k req | Easiest drop-in. Change the scrape URL to `http://api.scraperapi.com?api_key=KEY&url=ORIGINAL_URL`. Handles CAPTCHAs and IP rotation automatically. |
| **Oxylabs** | ~$15/GB for residential proxies | Enterprise-grade rotating residential IPs. Overkill for personal use. |
| **Bright Data** | ~$10.50/GB residential, pay-as-you-go | Similar to Oxylabs. Large proxy pool. Best for high-volume production scraping. |

#### Free alternatives

| Option | Notes |
|--------|-------|
| **Amazon Product Advertising API (PA-API)** | Official Amazon API, completely free. Requires an Amazon Associates account (free to create, but needs 3 qualifying sales to stay active). Has a `getItems` endpoint that returns reviews. Most reliable long-term option for Amazon data. |
| **Tor proxy** | Free rotating IPs via the Tor network. Slow (~1–3s per request) and Amazon frequently blocks known Tor exit nodes. Works intermittently. |
| **Rely on Reddit + YouTube** | For personal use, Reddit and YouTube comments often provide richer, more opinionated text than star-rated reviews. ReviewLens produces meaningful analysis with just these two sources if Amazon/Best Buy are blocked. |

#### Recommendation

For a personal local tool: **just use Reddit + YouTube**. Fill in the free API credentials and you'll get hundreds of detailed opinions without any proxy.

For a more reliable Amazon integration: **Amazon PA-API** is the best free option. Add a `scrapers/amazon_paapi.py` that calls the `GetItems` endpoint with your Associates credentials as a drop-in replacement for the Playwright scraper.

For production or commercial use: **ScraperAPI** at $29/mo is the simplest upgrade — a one-line URL change in `scrapers/amazon.py` and `scrapers/bestbuy.py`.

---

### Other ideas

- **More sources** — Walmart reviews, Google Shopping, Trustpilot, G2 (for software products)
- **Better LLM** — Swap Mistral for `llama3.2:70b` or `mixtral:8x7b` for higher-quality summaries (requires more RAM)
- **Scheduled re-analysis** — Cron job to re-scrape and re-analyze saved products weekly, tracking score changes over time
- **Browser extension** — Inject the ReviewLens verdict directly into Amazon product pages while you browse
- **Comparison mode** — Analyze two products side by side with a diff view of aspect scores

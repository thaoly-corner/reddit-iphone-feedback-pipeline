# BrandVoice — application layer

Web application that turns the ten Gold marts of the Reddit iPhone VoC pipeline into a tool for four user groups (Product Manager, Customer Experience Analyst, Brand Manager, Marketing Analyst). It covers BR01–BR10 and ships its own evaluation page (data correctness checks, API latency, BR coverage).

```
PostgreSQL (gold_* serving tables, RDS)
        ↓  parameterised SQL + TTL cache + label canonicalisation
application/api   FastAPI, /api/v1/*            (python 3.12, pandas, SQLAlchemy)
        ↓  JSON envelopes {data, meta}
application/web   React 19 + TypeScript + Vite  (ECharts, TanStack Query, Tailwind v4)
```

## Run with Docker (recommended for the demo)

Requires the repository `.env` with `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` pointing at the serving database.

```bash
docker compose up --build
# web  → http://localhost:8080
# api  → http://localhost:8000/api/docs
```

## Run locally for development

```bash
# API
cd application/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Web (proxies /api to :8000)
cd application/web
npm install
npm run dev            # http://localhost:5173
```

## Tests

```bash
cd application/api && pytest            # 4 canonicalisation unit tests + 28 contract tests against the live DB
cd application/web && npm run build     # type-check + production build
```

## Pages ↔ business requirements

| Page | BR | Gold mart | Endpoints |
|---|---|---|---|
| `/overview` | BR01 | `gold_feedback_volume` (+ `gold_issue_summary` when sliced) | `/volume/daily` `/volume/weekly` `/volume/summary` `/volume/peaks` |
| `/issues` | BR02, BR07 | `gold_issue_summary`, `gold_issue_trends` | `/issues/ranking` `/issues/detail` `/issues/trends` |
| `/emerging` | BR03 | `gold_emerging_issues` | `/emerging/alerts` `/emerging/series` `/emerging/heatmap` |
| `/sentiment` | BR04 | `gold_sentiment_summary`, `gold_issue_summary` | `/sentiment/timeline` `/sentiment/by-issue` `/sentiment/by-model` |
| `/features` | BR05 | `gold_feature_feedback` | `/features/matrix` |
| `/complaints` | BR06 | `gold_high_impact_complaints` | `/complaints` |
| `/compare` | BR08 | `gold_model_comparison` | `/compare/options` `/compare/models` `/compare/ios` `/compare/generations` |
| `/support` | BR09, BR10 | `gold_recurring_issues`, `gold_support_demand` | `/recurring` `/support/demand` |
| `/pipeline` | Evaluation | all + `fact_feedback_summary` | `/pipeline/evidence` `/pipeline/latency` `/meta/*` |

Global filters live in the URL (`?date_from=&date_to=&model=&ios=&feature=&issue=`) so any view can be shared or linked from slides. The persona switcher re-orders navigation, picks a landing page and changes KPI vocabulary; it is stored in `localStorage`.

## Design notes

- Look: cool neutral "ops console" (light grey / near-black), panels with hairline borders, horizontal nav, pill controls.
- Typography: Bricolage Grotesque for headlines and KPIs, Manrope for UI, IBM Plex Mono (tabular) for every number.
- One accent colour (electric blue) plus a lime signal colour for live/alert cues; categorical hues are assigned to **feature areas** in a fixed order and validated for colour-vision deficiency in both light and dark mode (see `src/lib/palette.ts`). Sentiment uses a fixed green / grey / red triad; status colours (watch / elevated / critical) are never reused for series.
- Every section carries an evidence line (BR id, mart, endpoint, rows, response time) so a reviewer can trace each chart back to the pipeline.
- Each page opens with a "lead": one sentence generated from the data that states the finding before the charts.

## Known data limitations handled in the API

`app/canonical.py` folds raw Silver labels (`iPhone 13Pro`, `İphone 13`, `iPhone16 Promax` → `iPhone 13 Pro`, `iPhone 16 Pro Max`) and rejects impossible products (`iPhone 3 Pro`, `iOS 24.5`). Filters are expanded back to the raw spellings in SQL. Once the Silver extractor is fixed upstream and the marts are re-run, this layer becomes an identity mapping. BR06 defaults to hiding `Non-Defect / General Inquiry` posts because the Gold mart does not exclude them.

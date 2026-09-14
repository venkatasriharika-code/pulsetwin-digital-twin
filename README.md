# PulseTwin — Milestone 1

PulseTwin is the hospital emergency-ward digital twin from the original prototype. Milestone 1 adds persistent storage and an editable hospital baseline.

## What changed

- PostgreSQL-first persistence using `DATABASE_URL` and `psycopg`.
- Automatic local SQLite fallback when `DATABASE_URL` is not set.
- Persisted hospital configuration, scenarios, and decisions.
- New `/config` hospital configuration screen.
- Baseline settings now drive `/api/status` and scenario evaluation:
  - Arrivals per hour
  - Doctors
  - Nurses
  - Beds
  - Triage nurses
  - CT capacity
  - Lab capacity
  - Doctor minutes per patient
  - Critical / serious / mild acuity mix

## Run locally with SQLite fallback

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# another terminal
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/config` to edit the hospital baseline. Changes persist to `backend/pulsetwin.db` by default.

## Run with PostgreSQL

Create a database and set the connection string before starting the API:

```bash
export DATABASE_URL='postgresql://pulsetwin:password@localhost:5432/pulsetwin'
cd backend
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on application startup. The adapter uses PostgreSQL JSONB for payloads and SQLite TEXT JSON when running locally.

## New API endpoints

```text
GET /api/config
PUT /api/config
```

The existing endpoints remain available, including `/api/status`, scenario parsing/evaluation, ward state, and decision history.

## Verification

The Milestone 1 verification covers backend compilation, frontend production build, configuration save/load, status recalculation after a configuration change, and decision persistence.

## Milestone 2: real-time simulation

Ward Twin now includes a WebSocket endpoint:

```text
/ws/simulation
```

The client sends an initialization message such as:

```json
{"action":"tick","tickMinutes":5,"tickSeconds":1,"demandMultiplier":1.0,"seed":42}
```

The server streams `connected` and `tick` messages containing live patient stages, event logs, doctor/bed/nurse utilization, throughput, and dynamic queue metrics. Supported actions are `tick`, `reset`, and `stop`.

The engine advances virtual time in five-minute steps and models stochastic arrivals, severity-priority doctor queues, service timers, testing, treatment, bed blocking, discharges, and queue wait accumulation. The Ward Twin page can start, advance, reset, and stop the stream without losing the existing scenario snapshot workflow.

## Milestone 3: predictive analytics

The backend now contains a real training pipeline in `backend/app/ml.py` and model endpoints:

```text
POST /api/ml/train
GET  /api/ml/status
POST /api/ml/predict
```

The trainer expects the public CMS **Timely and Effective Care — Hospital** CSV. It filters Emergency Department measures, aggregates hospital rows, and trains:

- A `RandomForestRegressor` for median ED time (`OP_18a`), reporting MAE, RMSE, and R².
- A class-balanced `RandomForestClassifier` for high-wait bottleneck risk, reporting accuracy, balanced accuracy, precision, recall, and F1.

The expected benchmark is published by the [CMS Provider Data Catalog](https://data.cms.gov/provider-data/dataset/yv7e-xc69). Its documented bulk CSV is:

```text
https://data.cms.gov/provider-data/sites/default/files/resources/0437b5494ac61507ad90f2af6b8085a7_1785189967/Timely_and_Effective_Care-Hospital.csv
```

Place that file at `backend/data/cms_timely_effective_care_hospital.csv`, or set `PULSETWIN_ML_DATASET` to an approved local file. The trainer refuses to fabricate fallback records and returns a clear error when the dataset is absent or too small. This CMS benchmark is hospital-level operational data; patient-level models require approved MIMIC-IV-ED or hospital data and should not be inferred from this aggregate benchmark.

Trained artifacts are saved outside source control under `backend/models/` by default. Set `PULSETWIN_MODEL_DIR` to change the artifact location.

## Milestone 4: anomaly detection and predictive alerting

The live simulation now runs a hybrid anomaly detector in `backend/app/anomaly.py`. It combines rolling queue history with operational guardrails:

- Arrival-rate surge versus configured baseline
- Doctor utilization pressure
- Priority and bed queue thresholds
- Rolling queue z-score anomaly detection
- A bounded predictive surge probability

Each live tick may include an `anomaly` payload with alert records, probability, signals, and anomaly state. Alerts are persisted in PostgreSQL/SQLite and are available through:

```text
GET /api/alerts
```

The Ward Twin shows live surge probability and explainable alert messages. The `/alerts` Alert Center shows historical alert records and recommended actions. High-demand simulation tests generate critical ED surge alerts and queue-growth alerts; normal operation does not require fabricated historical data.

## Milestone 5: automated resource reallocation

PulseTwin now provides surge-driven staffing recommendations through `backend/app/reallocation.py`. Plans combine predicted surge probability, queue pressure, doctor utilization, and bed utilization to produce explainable actions, shift-by-shift coverage, confidence, and safety guardrails.

New endpoints:

```text
GET  /api/recommendations
POST /api/recommendations/generate
POST /api/recommendations/{id}/apply
```

The live WebSocket simulation automatically generates and persists a proposed staffing plan when surge probability reaches 45% or higher. Applying a plan updates the persisted hospital baseline; the UI labels this action clearly and retains guardrails for human review.

The `/staffing` Staffing Ops screen provides plan generation, current/next/following-shift recommendations, resource reallocations, confidence, and an Apply to baseline control.

## Vercel deployment

The repository includes `vercel.json` for deploying the React/Vite frontend from the `frontend` directory. Import this repository into Vercel with the default project settings; Vercel will run the frontend build and serve the SPA routes correctly. Set `VITE_API_BASE_URL` in the Vercel project environment variables to the deployed FastAPI backend URL so the live simulation, alerts, recommendations, persistence, and model APIs work in production. The local development default remains `http://localhost:8000`.

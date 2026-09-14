# PulseTwin — Frontend

React + TypeScript + Vite frontend for the four-screen flow: **Command Center →
Ask → Recommendation → Ward View**.

## Run it

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL to your backend
npm run dev
```

## Structure

```
src/
  api/
    types.ts     # shared request/response types — this is the contract with your backend
    client.ts     # every fetch call goes through here
  components/     # Sidebar, KpiTile, SeverityBadge, ScoreBar
  pages/
    CommandCenter.tsx    # GET /api/status
    AskScenario.tsx      # POST /api/scenario/parse
    Recommendation.tsx   # POST /api/scenario/evaluate
    WardView.tsx         # GET /api/ward/state
  App.tsx          # routes + flow state (scenario, selected candidate)
```

## API contract your backend needs to implement

| Method | Path                  | Purpose                                                              |
| ------ | --------------------- | --------------------------------------------------------------------- |
| GET    | `/api/status`         | Current live KPIs for the Command Center                              |
| POST   | `/api/scenario/parse` | `{ question }` → structured `ParsedScenario`                          |
| POST   | `/api/scenario/evaluate` | `{ scenario }` → `EvaluationResult` (baseline + candidates + recommendation) |
| GET    | `/api/ward/state?scenarioId=&candidateId=` | Digital-twin patient/stage state for a chosen candidate |

Exact shapes are in `src/api/types.ts`. Each page shows a loading state, an
explicit error state with retry, and never silently falls back to fake data —
if a call fails, the person sees why and can retry once the backend is up.

## Notes

- All API calls are centralized in `src/api/client.ts` — point
  `VITE_API_BASE_URL` at your backend and everything else works unchanged.
- No third-party UI kit; styling is plain CSS with design tokens in
  `src/styles/global.css` (colors, fonts) so the look is easy to retheme in
  one place.

# Waypoint

Cash-flow-aware decision engine. HackPSU Fall 2026. See `SPEC.md` (full handoff) and `CLAUDE.md` (working rules).

```
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Python 3.12
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
./scripts/ci.sh
```

Session status: `docs/STATUS.md`.

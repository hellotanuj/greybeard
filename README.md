# Greybeard

An AI teammate that remembers every repair. Greybeard compares general troubleshooting with advice grounded in 18 months of fictional field-service history.

## Try the demo

1. Select **See memory in action** or choose one of five jobs.
2. Select **Compare repair advice** to see the difference that memory makes.
3. Explore the cited repair history, change the memory horizon, or record an outcome.
4. Open **What we’ve learned** for fleet patterns, or **Ask Greybeard** for questions in plain language.

All companies, people, equipment and job records in the bundled dataset are fictional. Repair guidance is a demonstration and should be reviewed by a qualified technician before use on real equipment.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Add a real HINDSIGHT_API_KEY to .env.
PYTHONPATH=backend uvicorn greybeard.main:app --reload
```

## Deploy on Vercel

Import this repository with Application Preset **FastAPI**. Add `HINDSIGHT_API_KEY` and `HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io` to the project environment, then deploy. `api/index.py` exposes the FastAPI application.

Set up the memory banks from a trusted local environment using `python scripts/seed.py`. The public deployment intentionally disables the bulk bootstrap endpoint. The optional baseline LLM settings are described in `.env.example`; without them, Hindsight uses an empty bank for the baseline.

## Architecture and limits

- Vanilla JavaScript, bundled variable fonts, responsive CSS and reduced-motion support.
- FastAPI routes for dispatch, comparisons, evidence, history, close-outs and questions.
- Hindsight retain, recall and reflect, with structured briefings and cited work orders.
- Four memory horizons, including an empty Day-1 bank.
- The dispatch board is demonstration state. On Vercel its temporary state can reset or differ across function instances; Hindsight retains submitted learning independently. This is not a production work-order system.
- Public inference and close-outs consume the owner’s Hindsight allowance. Add authentication and shared rate limiting before a broad production launch.
- No API keys are shipped to the browser or committed to this repository.

## Tests

```sh
pytest -q
```

Tests use a stand-in Hindsight client. Live service validation is separate.

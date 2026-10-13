# Mini Order Synchronizer

FastAPI service that fetches raw orders from `SOURCE_URL`, normalizes Russian phone numbers, drops invalid numbers, deduplicates by phone and returns the winning record.

## Public endpoint

`GET /api/clients`

Response shape:
- `clients`: `name`, normalized `phone`, `email`, `amount`
- `stats`: `received`, `unique`, `duplicates_merged`, `invalid_dropped`

The endpoint is deterministic and stateless: each request recomputes the same result from the source API, so repeat requests do not create records or duplicate state.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Optional environment variable: `SOURCE_URL` (defaults to the assignment's source API). Do not commit credentials or `.env` files.

## Deploy to Render

1. Push this repository to GitHub.
2. In Render, choose **New + → Blueprint**, connect the repository, and deploy using `render.yaml`.
3. Open `https://YOUR-SERVICE.onrender.com/api/clients` and confirm it returns the required JSON.
4. Submit the repository URL and that endpoint URL.

## Rules

- 10 digits: prepend country code `7`.
- 11 digits starting with `8`: replace the first digit with `7`.
- 11 digits starting with `7`: keep as-is.
- Other formats are rejected.
- Duplicate winner: highest numeric `amount`; on a tie, latest parsed `created_at`.
- Invalid or missing timestamps sort before valid timestamps.

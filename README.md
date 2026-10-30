# Nexora Business Studio V4

A colorful, responsive local business management application built with FastAPI, SQLite and vanilla JavaScript. Features customer and product CRUD, order creation/status management, stock updates, search/filter, analytics, and CSV export.

## Run on Windows

Open a terminal inside the `nexora-v4` folder and run these commands separately:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000

Database file `nexora.db` is automatically created in the project folder. No login is included. This is a **local portfolio demo**, not a secure multi-user hosted SaaS. Do not expose it to the public internet without adding authentication, authorization, CSRF protections where applicable, and other production security measures.

Note: SQLite stores data locally. Orders are not editable or deletable; their status can be changed, including cancellation with stock restoration. Prices are in USD for this demo.

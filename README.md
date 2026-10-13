
## Frontend

The frontend foundation uses React, Vite, and React Router. Node.js 18+ and npm
are required.

```powershell
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`. Course creation is currently a
visual placeholder; persistence and course APIs will be added in a later step.
Backend requests belong in `frontend/lib/api.js`; set `VITE_API_BASE_URL` when
the API is available.

Run the backend separately with:

```powershell
python -m uvicorn backend.main:app --reload
```

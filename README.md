# SEOProject

This project is a small full‑stack SEO analysis tool with:

- A **FastAPI** backend (`backend/`) that fetches and analyzes web pages.
- A **React + Vite** frontend (`frontend/`) that shows SEO highlights, score, previews, and recommendations.

The instructions below assume **Windows + PowerShell**.

---

## 1. Install all requirements

From the project root:

```powershell
cd "C:\Users\doref\OneDrive\שולחן העבודה\פרוייקטים\תואר שני\שנה ב\פיתוח מערכות בינה מלאכותית\SEOProject"
.\setup_project.ps1
```

This will:

- Create a Python virtual environment at `.venv/` (if it does not exist).
- Install backend Python dependencies from `backend/requirements.txt`.
- Run `npm install` in the `frontend/` directory.

You can skip parts if needed:

```powershell
.\setup_project.ps1 -SkipPython   # only install npm deps
.\setup_project.ps1 -SkipNode     # only install Python deps
```

> If you see an error like *"running scripts is disabled on this system"*, allow local scripts once:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

---

## 2. Run the project

From the project root, run:

```powershell
.\run_project.ps1
```

This opens two new PowerShell windows:

- **Backend** – runs:

  ```powershell
  python -m backend.main
  ```

- **Frontend** – runs (inside `frontend/`):

  ```powershell
  npm run dev
  ```

Then open the app in your browser:

- Frontend: `http://localhost:5173`
- Backend health check: `http://127.0.0.1:8000/api/health`

You can start only one side if needed:

```powershell
.\run_project.ps1 -NoBackend   # only frontend
.\run_project.ps1 -NoFrontend  # only backend
```

---

## 3. Development notes

- **Backend**: main entry is `backend/main.py`, core logic in `backend/seo_analyzer.py`.
- **Frontend**: main UI in `frontend/src/App.jsx`, bootstrapped via Vite in `frontend/src/main.jsx`.

Feel free to adjust the scripts if your Python / Node versions or paths differ.  
All paths in this README are based on the current user directory and project location.



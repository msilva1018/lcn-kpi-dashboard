# LCN Consulting — 2026 KPI Dashboard

A clean, editable KPI dashboard built with **Streamlit**, hosted on **GitHub** and
deployed on **Streamlit Community Cloud**, backed by a **Google Sheet** so your
edits persist automatically and the dashboard is always up to date — no manual
re-uploading.

## Sections
1. **KPI Scorecard** — 0–6 / 6–12 month targets, status, and notes per metric.
2. **Open Bids Pipeline** — editable opportunities with auto-calculated Active Opps, Clients, Win Rate.
3. **Account Strategy** — the three tiers (Active / Dormant / Cold) with editable priorities and goals.
4. **H2 Monthly Tracker** — monthly LinkedIn KPIs with auto-calculated H2 Total/Avg and vs Target.

---

## How persistence works
The app reads and writes a Google Sheet. Edit a value in the web UI → it saves to
the Sheet (auto-save is on by default) → every visit loads the current data. You
can also edit the Sheet directly; click **🔄 Refresh from source** to re-pull.

If Google Sheets credentials aren't configured, the app runs in **local mode**
using `data.json` (fine for previewing, but edits won't persist on the cloud).

---

## One-time Google Sheets setup (~10 min)
1. **Google Cloud Console** → create or pick a project.
2. **APIs & Services → Enable APIs** → enable **Google Sheets API** and **Google Drive API**.
3. **Credentials → Create credentials → Service account**. Give it a name, create it.
4. Open the service account → **Keys → Add key → JSON**. Download the JSON file.
5. Create a **blank Google Sheet** in your Drive. Copy its URL.
6. Click **Share** on the Sheet and add the service account's `client_email`
   (looks like `...@...iam.gserviceaccount.com`) as an **Editor**.
7. Add your secrets (see `.streamlit/secrets.toml.example`):
   - **Locally:** copy it to `.streamlit/secrets.toml` and fill in the values.
   - **On Streamlit Cloud:** App → **Settings → Secrets**, paste the same content.

On first load the app auto-creates the worksheets (`scorecard`, `pipeline`,
`strategy`, `h2`) and seeds them from `data.json`. You're done — start editing.

> You create the Google Cloud service account and share the Sheet yourself
> (account creation and sharing can't be done on your behalf).

---

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push to GitHub:
   ```bash
   git init && git add . && git commit -m "KPI dashboard"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. **share.streamlit.io → New app** → pick repo, branch `main`, file `app.py` → **Deploy**.
3. Add your secrets under **Settings → Secrets**. The live URL updates automatically.

## Files
| File | Purpose |
|------|---------|
| `app.py` | Dashboard UI |
| `storage.py` | Google Sheets backend + local JSON fallback |
| `data.json` | Seed values (used to bootstrap the Sheet / local mode) |
| `.streamlit/config.toml` | Brand theme |
| `.streamlit/secrets.toml.example` | Template for Google credentials |
| `requirements.txt` | Dependencies |

## Optional next step
You have **HubSpot** connected — the Pipeline tab could auto-sync deals/opps from
HubSpot instead of manual entry. Ask and it can be wired up.

# Setup Guide — LCN KPI Dashboard
**From a blank Google Sheet to a live, always‑up‑to‑date Streamlit app.**

Work top to bottom. Total time ≈ 20–30 min. You'll need a Google account and a
GitHub account (both free). Check each box as you go.

---

## Checklist overview
- [ ] **Phase A** — Google Cloud: project + enable 2 APIs
- [ ] **Phase B** — Create a service account + download its JSON key
- [ ] **Phase C** — Create a Google Sheet + share it with the service account
- [ ] **Phase D** — Put the project on GitHub
- [ ] **Phase E** — Deploy on Streamlit + paste your secrets
- [ ] **Phase F** — Verify it's connected and start editing

---

## Phase A — Google Cloud project & APIs

1. Go to **https://console.cloud.google.com/** and sign in.
2. **Create a project:** click the project dropdown in the top bar (left of the
   search box) → **New Project** → name it `kpi-dashboard` → **Create**. Wait a few
   seconds, then make sure that project is selected in the dropdown.
3. **Enable the Sheets API:** in the top search bar type **Google Sheets API** →
   open it → click **Enable**.
4. **Enable the Drive API:** search **Google Drive API** → open it → **Enable**.
   *(Both are required — the app opens the Sheet via Drive and reads/writes via Sheets.)*

✅ When done, both APIs show "API Enabled".

---

## Phase B — Service account & JSON key

A *service account* is a robot Google account your app logs in as.

1. Left menu (☰) → **APIs & Services → Credentials**.
   *(Or ☰ → IAM & Admin → Service Accounts — either path works.)*
2. Click **+ Create credentials → Service account**.
3. **Service account name:** `kpi-dashboard` → **Create and continue**.
4. **Grant access step:** you can skip this — click **Continue**, then **Done**.
   *(This role is about Cloud project access, not your Sheet.)*
5. You're back on the Credentials list. Under **Service Accounts**, click the new
   account's **email** to open it.
6. Open the **Keys** tab → **Add key → Create new key** → choose **JSON** → **Create**.
7. A `.json` file downloads automatically. **Keep it safe** — it's the only copy and
   it's your app's password. Don't email it or commit it to GitHub.

✅ You now have a file like `kpi-dashboard-xxxxx.json` and a service‑account email
that looks like `kpi-dashboard@kpi-dashboard.iam.gserviceaccount.com`.

---

## Phase C — Google Sheet & sharing

1. Go to **https://sheets.new** to create a **blank** Google Sheet.
2. (Optional) Rename it, e.g. *"LCN KPI Data"*. **Don't add any tabs or headers** —
   the app builds them automatically on first run.
3. Copy the **full URL** from the address bar (the long
   `https://docs.google.com/spreadsheets/d/.../edit` link).
4. Click the green **Share** button (top‑right).
5. In **Add people**, paste the **service‑account email** from Phase B.
6. Set its access to **Editor** → untick "Notify people" → **Share** / **Send**.

✅ The service account now has Editor access to your blank Sheet.

---

## Phase D — Put the project on GitHub

Pick **one** of the three methods.

### Option 1 — GitHub Desktop (easiest, no terminal)
1. Install **GitHub Desktop** (desktop.github.com) and sign in.
2. **File → New repository** (or **Add → Add existing repository** if you point it at
   the unzipped `lcn-kpi-dashboard` folder). Name it `lcn-kpi-dashboard`. You can
   keep it **Private**.
3. Copy all the project files into that repository folder if they aren't there
   already.
4. In Desktop you'll see the files listed as changes. Add a summary like
   `KPI dashboard`, click **Commit to main**, then **Publish repository**.

### Option 2 — Command line (Git installed)
In a terminal opened inside the `lcn-kpi-dashboard` folder:
```bash
git init
git add .
git commit -m "KPI dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
(Create the empty repo first at github.com → **New repository**.)

### Option 3 — GitHub web upload (no tools at all)
1. github.com → **New repository** → name `lcn-kpi-dashboard` → **Create**.
2. On the repo page → **Add file → Upload files**.
3. Drag in **every file**, including the `.streamlit` folder
   (`config.toml` and `secrets.toml.example`). Then **Commit changes**.

> ⚠️ **Never upload your real `secrets.toml` or the JSON key.** The `.gitignore`
> already blocks `secrets.toml`; with web upload, simply don't drag those files.
> Only the `secrets.toml.example` template should be in the repo.

✅ Your repo shows `app.py`, `storage.py`, `data.json`, `requirements.txt`,
`README.md`, and the `.streamlit/` folder.

---

## Phase E — Deploy on Streamlit + secrets

1. Go to **https://share.streamlit.io** → **Sign in with GitHub** → **Authorize
   Streamlit** so it can see your repos. Accept the terms.
2. In your workspace, click **Create app** (upper‑right) → choose
   **Deploy a public app from GitHub** (private repos work too).
3. Fill in:
   - **Repository:** `<your-username>/lcn-kpi-dashboard`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **(Optional) App URL:** pick a memorable subdomain, e.g. `lcn-kpi`.
4. Click **Advanced settings** → find the **Secrets** box.
5. Open your downloaded JSON key in a text editor and the file
   `.streamlit/secrets.toml.example` from the project. **Paste this into the Secrets
   box**, filling every value from your JSON and your Sheet URL:
   ```toml
   sheet_url = "https://docs.google.com/spreadsheets/d/PASTE_YOUR_SHEET_ID/edit"

   [gcp_service_account]
   type = "service_account"
   project_id = "kpi-dashboard"
   private_key_id = "from your JSON"
   private_key = "-----BEGIN PRIVATE KEY-----\n....\n-----END PRIVATE KEY-----\n"
   client_email = "kpi-dashboard@kpi-dashboard.iam.gserviceaccount.com"
   client_id = "from your JSON"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "from your JSON"
   universe_domain = "googleapis.com"
   ```
   **Critical:** copy `private_key` **exactly** as it appears in the JSON, including
   every `\n`. Keep it on one line wrapped in double quotes. This single field is
   the #1 cause of failures.
6. Click **Save** on secrets, then **Deploy**. Watch the build log on the right;
   first deploy takes a few minutes while it installs dependencies.

✅ When it finishes you get a live URL like `https://lcn-kpi.streamlit.app`.

---

## Phase F — Verify & use

1. Open your app URL. In the **sidebar** you should see
   **🟢 Connected to Google Sheets — edits save permanently.**
2. Open your Google Sheet in another tab — you'll now see four tabs at the bottom:
   `scorecard`, `pipeline`, `strategy`, `h2`, pre‑filled with your KPI data. The app
   created them.
3. In the app, change any value (e.g. a Win Probability or a monthly number). With
   **Auto‑save** on (default), it writes to the Sheet within a second — you'll see a
   💾 "Saved" toast. Refresh the app: your change is still there.

🎉 That's it. The dashboard is now always current — edit it anytime in the browser,
from anywhere, and it persists. You can also edit the Google Sheet directly and hit
**🔄 Refresh from source** in the app to pull those changes in.

---

## Day‑to‑day use
- **Edit in the app:** type in any tab; auto‑save persists it. Or turn auto‑save off
  and use **💾 Save now**.
- **Add/remove rows** in the Scorecard or Pipeline: use the **＋** at the bottom of
  the table, or select a row's checkbox and delete.
- **Back up:** sidebar **⬇️ Export data.json** downloads a snapshot anytime.
- **Reset:** sidebar **Reset to seed values** restores the original KPIs.
- **Update the look or logic later:** edit the code on GitHub (or push from Desktop);
  Streamlit redeploys automatically within a minute.

---

## Troubleshooting (matches the messages the app shows)

**Sidebar says 🟡 "Local mode (no persistence)."**
Secrets weren't found. In Streamlit: **Manage app → Settings → Secrets**, confirm the
TOML is pasted and saved, then **Reboot** the app. Make sure the section header is
exactly `[gcp_service_account]` and `sheet_url` is at the top (not inside the section).

**Red error mentioning `PERMISSION_DENIED` / "has not been used in project … or it is disabled".**
An API isn't enabled. Re‑do **Phase A** — enable **both** Google Sheets API and
Google Drive API in the *same* project as your service account, then reboot.

**Red error mentioning `SpreadsheetNotFound` or 403 on opening the sheet.**
The Sheet isn't shared with the robot, or the URL is wrong. Re‑do **Phase C**: open
the Sheet → **Share** → add the `client_email` as **Editor**. Confirm `sheet_url`
matches that exact Sheet.

**Error like `Could not deserialize key data` / `Invalid private key` / `invalid_grant`.**
The `private_key` got mangled. Re‑paste it from the JSON, keeping all `\n` characters
and the `-----BEGIN/END PRIVATE KEY-----` markers, on one quoted line.

**Build fails on dependencies.**
Confirm `requirements.txt` is in the repo root and lists `streamlit`, `pandas`,
`gspread`, `google-auth`. Check the build log for the offending line.

**App is blank or shows old code.**
**Manage app → Reboot.** Code/data changes pushed to GitHub redeploy automatically,
usually within a minute.

**I edited the Sheet directly but the app shows old numbers.**
Click **🔄 Refresh from source** in the sidebar (the app caches data per session).

---

## What lives where
| Where | What |
|-------|------|
| **Google Sheet** | Your live data (4 tabs). Source of truth. |
| **GitHub repo** | The app code + the seed `data.json`. |
| **Streamlit Cloud** | Runs the app and holds your secrets (credentials). |
| **The JSON key file** | Stays on your computer / in Streamlit secrets only. Never in GitHub. |

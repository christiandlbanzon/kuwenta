# Deploy Kuwenta

Two services: backend on **Fly.io** (Singapore, free tier), frontend on **Vercel** (free tier).
End-to-end deploy takes ~15 minutes the first time.

> **Why I can't run these for you:** Fly.io and Vercel both need browser-based login that
> opens a tab on your machine. Once you've authed once, every command below is copy-paste.

---

## 1. Backend → Fly.io

### One-time setup

```bash
# Install flyctl (Windows PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

# Or on Mac/Linux
curl -L https://fly.io/install.sh | sh

# Sign in (opens browser)
fly auth signup    # if you don't have an account
fly auth login     # if you do
```

### Launch the app

From `backend/`:

```bash
cd backend

# Creates the app on Fly. The fly.toml in this directory is the config — accept it.
# Use a unique app name (will be the URL: <name>.fly.dev)
fly launch --copy-config --no-deploy --name kuwenta-yourname

# Create the persistent volume for SQLite + receipt images (1 GB free)
fly volumes create kuwenta_data --size 1 --region sin

# Set production secrets
fly secrets set KUWENTA_GEMINI_API_KEY="<your gemini key>"
fly secrets set KUWENTA_JWT_SECRET="$(openssl rand -base64 48)"
# (PowerShell: $secret = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48)); fly secrets set KUWENTA_JWT_SECRET="$secret")

# Deploy
fly deploy
```

After deploy, your backend lives at `https://kuwenta-yourname.fly.dev`.
Verify: `curl https://kuwenta-yourname.fly.dev/healthz` → `{"status":"ok"}`.

### Updating the backend

Subsequent deploys:

```bash
fly deploy
```

Or wire up the GitHub Actions workflow at `.github/workflows/deploy.yml` — it'll
auto-deploy on every push to main. You'll need to add the `FLY_API_TOKEN` GitHub secret:

```bash
fly tokens create deploy
# Copy the token, then in your GitHub repo:
# Settings → Secrets and variables → Actions → New repository secret
# Name: FLY_API_TOKEN, value: <paste>
```

### Updating the CORS origin (important!)

Once you have the Vercel URL (next section), update the backend's CORS to allow it.
Edit `backend/app/main.py`:

```python
allow_origins=["http://localhost:3000", "https://your-frontend.vercel.app"],
```

Commit + redeploy.

---

## 2. Frontend → Vercel

### Easiest path: GitHub-connected import

1. Push the repo to GitHub
2. Go to https://vercel.com/new
3. Import the Kuwenta repo
4. **Root directory:** `frontend`
5. **Framework preset:** Next.js (auto-detected)
6. **Environment variables:**
   - `KUWENTA_API_URL` = `https://kuwenta-yourname.fly.dev` (your Fly.io URL from step 1)
7. Click **Deploy**

Done. Vercel auto-deploys on every git push.

### CLI path (if you prefer)

```bash
cd frontend
npm install -g vercel
vercel login
vercel --prod
# Follow prompts; when asked for env vars, set KUWENTA_API_URL to your Fly URL
```

---

## 3. Post-deploy checklist

- [ ] `https://your-frontend.vercel.app` loads the landing page
- [ ] Sign up creates a real user (check `fly logs` for SIGNUP request)
- [ ] Login + dashboard works
- [ ] Quick-add hits Gemini and returns a draft (this is the moneyshot demo)
- [ ] `/admin/llm-stats` shows your real usage
- [ ] Receipt upload works (snap a Jollibee receipt!)
- [ ] CORS isn't blocking — if it is, see "Updating the CORS origin" above

## 4. Cost expectations

- **Fly.io:** Free tier covers 3 shared-CPU-1x VMs + 3 GB volumes + 160 GB outbound.
  Auto-stop is enabled (`auto_stop_machines = "stop"`) so the app sleeps when idle —
  first request after sleep takes ~3s to spin up. Keep this; it's free.
- **Vercel:** Free hobby tier. Unlimited static + 100 GB bandwidth.
- **Gemini:** Free tier, 250 req/day on 2.5-flash. Plenty for a personal app.

**Total: $0/month** as long as you stay on free tiers.

## 5. Environment variables — full reference

Every backend env var is `KUWENTA_`-prefixed to avoid collisions with system env.

| Variable | Where to set | Example |
|---|---|---|
| `KUWENTA_GEMINI_API_KEY` | Fly.io secrets | `AIzaSy...` |
| `KUWENTA_JWT_SECRET` | Fly.io secrets | `<48-byte random>` |
| `KUWENTA_DATABASE_URL` | Fly.io env (in fly.toml) | `sqlite+aiosqlite:////data/kuwenta.db` |
| `KUWENTA_RECEIPT_STORAGE_DIR` | Fly.io env (in fly.toml) | `/data/receipts` |
| `KUWENTA_GEMINI_RATE_LIMIT_PER_MIN` | Fly.io env (in fly.toml) | `8` |
| `KUWENTA_API_URL` | Vercel env | `https://kuwenta-yourname.fly.dev` |

## 6. Troubleshooting

**Backend won't start — "alembic upgrade head" failing?**
Check `fly logs`. Usually missing `KUWENTA_DATABASE_URL` or volume not mounted.
`fly volumes list` should show `kuwenta_data` attached.

**Frontend can't reach backend — CORS errors?**
Update `allow_origins` in `app/main.py`, redeploy backend.

**Login works but dashboard is blank?**
Check the browser network tab → `/api/proxy/auth/me`. If it's 401, the JWT cookie
isn't being set or your JWT_SECRET is mismatched between deploys.

**429 Too Many Requests from Gemini?**
You hit the daily quota (250/day on free tier). Wait until midnight Pacific or
upgrade to paid. Backend retries 429 automatically, but if all retries fail it
surfaces the error.

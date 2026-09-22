# Dispense Lens - Vercel Deployment Guide

This guide covers deploying the **Dispense Lens (Next.js 16)** frontend to [Vercel](https://vercel.com).

---

## Architecture Overview

Dispense Lens is organized as a monorepo:
- **`frontend/`**: Next.js 16 (React 19, Tailwind CSS 4, Lucide Icons, Recharts) -> **Deploys directly to Vercel**.
- **`backend/`**: Python FastAPI + PostgreSQL (Alembic migrations, pgvector/psycopg 3) -> Deploys to Railway, Render, Fly.io, AWS, or any Docker VPS.

---

## Method 1: Deploy via Vercel Dashboard (Recommended)

This method provides continuous deployment (CI/CD) on every push to your GitHub branch.

### Step 1: Connect Repository to Vercel
1. Log in to [Vercel](https://vercel.com).
2. Go to **Dashboard** > **Add New...** > **Project** (or navigate to [vercel.com/new](https://vercel.com/new)).
3. Under **Import Git Repository**, select `ImLWChuen/dispense_lense_koi`.

### Step 2: Configure Project Settings (Crucial)
Because Dispense Lens is a monorepo, you **must set the Root Directory**:
- **Project Name**: `dispense-lens` (or your preferred name)
- **Framework Preset**: `Next.js`
- **Root Directory**: Click **Edit** and choose `frontend` (do **not** leave as root `./`).
- **Build and Output Settings**: Default (`npm run build` and `.next`)
- **Install Command**: Default (`npm install`)

### Step 3: Add Environment Variables
Under the **Environment Variables** section, configure:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://api.yourdomain.com/api/v1` | Public API URL for client-side API requests |
| `BACKEND_URL` *(Optional)* | `https://api.yourdomain.com` | Base backend URL if using Next.js server rewrites |

> **Note**: If your backend is not yet publicly deployed, you can temporarily set `NEXT_PUBLIC_API_URL` to `http://127.0.0.1:8000/api/v1` or leave it empty during initial preview testing.

### Step 4: Click Deploy
Click **Deploy**. Vercel will clone `frontend/`, run `npm install`, and execute `next build`. Within 1-2 minutes, you will receive a live URL:
`https://dispense-lens-<unique-hash>.vercel.app`

---

## Method 2: Deploy via Vercel CLI (Terminal)

You can also deploy directly from your local workstation using the Vercel CLI.

### Step 1: Authenticate with Vercel
From PowerShell in the project root:
```powershell
npx vercel login
```
*(Follow the browser prompt to complete authentication).*

### Step 2: Deploy Preview Build
Navigate into the `frontend` folder and run `npx vercel`:
```powershell
cd frontend
npx vercel
```
Answer the interactive setup questions:
- `Set up and deploy?` **Y**
- `Which scope?` Select your account
- `Link to existing project?` **N** (or **Y** if already created)
- `Project name?` `dispense-lens`
- `In which directory is your code located?` `./` (since you are inside `frontend`)

### Step 3: Deploy to Production
To promote your build to the production domain:
```powershell
npx vercel --prod
```

---

## Backend CORS Configuration

Once your Vercel deployment URL is generated (e.g. `https://dispense-lens.vercel.app`), update your backend's allowed CORS origins so requests are not blocked by browser security:

In your deployed backend environment settings (or `backend/.env`):
```ini
CORS_ORIGINS=https://dispense-lens.vercel.app,https://dispense-lens-*.vercel.app,http://localhost:3000,http://localhost:3001
```

---

## Verification & Status

- **Build Status**: Verified with Next.js 16.3.4 (Turbopack). All 15 static/dynamic routes compile with 0 errors.
- **CSS Block**: Dark mode CSS block in `app/globals.css` has been validated and closed.
- **Vercel Config**: `frontend/vercel.json` has been committed to the repository with the `nextjs` framework preset.

# SDLC DocGen - Railway.app Deployment Guide

## 🚀 Quick Start (3 minutes to live!)

### Step 1: Go to Railway.app
1. Visit: https://railway.app
2. Click "Start a New Project"
3. Select "Deploy from GitHub repo"

### Step 2: Connect GitHub & Select Repo
1. Authorize Railway to access your GitHub
2. Select: **Akshit-hanuai/SDLC-DOCGEN**
3. Choose main branch
4. Railway auto-detects docker-compose.yml ✅

### Step 3: Configure Services
Railway will show you the services from docker-compose.yml:
- `db` (PostgreSQL with pgvector)
- `git-server` 
- `backend` (FastAPI on :8000)
- `frontend` (React on :5173)

For each service, Railway auto-configures networking. ✅

### Step 4: Set Environment Variables
In Railway dashboard, for the **backend** service, add:

```
DATABASE_URL=postgresql+asyncpg://postgres:${{ Postgres.PASSWORD }}@${{ Postgres.HOST }}:5432/docgen
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:0.5b
LLM_MODE=vllm
PORT=8000
```

(Railway provides `Postgres.PASSWORD` and `Postgres.HOST` automatically)

### Step 5: Deploy!
Click "Deploy" button
⏳ Wait 2-3 minutes...

### Step 6: Get Your URL
Railway creates a public URL automatically:
```
https://sdlc-docgen-production.up.railway.app
```

✅ **Done!** Your app is live and shareable worldwide!

---

## 📊 What You Get (Free Tier)
- ✅ Permanent URL (24/7 availability)
- ✅ $5/month free credit
- ✅ Auto-scaling
- ✅ HTTPS/SSL included
- ✅ Database included
- ✅ Environment variable management

---

## 🔗 Share This URL
Once deployed, give people this link:
```
https://sdlc-docgen-production.up.railway.app
```

Everyone can access from any device, anywhere! 🌍

---

## 📝 Notes
- LLM extraction is disabled (set in config) for fast performance
- Database pool is optimized for concurrent users
- Free tier includes $5/month (more than enough for demo)
- Custom domain available if needed

---

## Troubleshooting

### App won't start?
1. Check Railway logs in dashboard
2. Verify environment variables are set
3. Make sure PostgreSQL service is healthy

### API returns 502?
Check that backend can reach database:
- Railway provides `Postgres.HOST` and `Postgres.PASSWORD`
- Update DATABASE_URL if needed

### Performance issues?
- LLM extraction is already disabled
- Database pool is optimized (20+30)
- Check Railway resource usage in dashboard

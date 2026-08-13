# Deploy SDLC-DocGen to Railway - Step by Step

## Prerequisites
- GitHub account (you have it!)
- Railway.app account

## Step 1: Create Railway Account
1. Go to https://railway.app
2. Click "Start Building"
3. Sign in with GitHub (use Akshit-hanuai)
4. Authorize Railway to access your repositories

## Step 2: Create New Project
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Select repository: **SDLC-DOCGEN**
4. Authorize if prompted

## Step 3: Add Services
Railway will auto-detect and create services. Add these:

### Service 1: Database (PostgreSQL)
1. Click "Add" → Select "PostgreSQL"
2. Railway adds PostgreSQL automatically
3. Note the connection details

### Service 2: Backend (FastAPI)
1. Click "Add" → "Docker"
2. Set:
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Watch Path:** `backend/`

3. Add Environment Variables (click on service → Variables):
   ```
   PORT=8000
   DATABASE_URL=postgresql+asyncpg://[user]:[password]@[host]:[port]/[database]
   GIT_REPOS_ROOT=/repos
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=qwen2.5:0.5b
   LLM_MODE=auto
   LLM_EXTRACTION_ENABLED=false
   ```

4. Add Port:
   - Container Port: 8000
   - Public Port: 8000

### Service 3: Frontend (React/Vite)
1. Click "Add" → "Docker"
2. Set:
   - **Dockerfile Path:** `frontend/Dockerfile`
   - **Watch Path:** `frontend/`

3. Environment Variables:
   ```
   VITE_API_URL=https://[your-backend-url].railway.app
   VITE_PROXY_TARGET=https://[your-backend-url].railway.app
   ```

4. Add Port:
   - Container Port: 5173
   - Public Port: 3000 (or any public port)

## Step 4: Deploy!
1. Click "Deploy" on each service
2. Wait for deployments to complete (3-5 minutes)
3. Your frontend URL will appear in Railway dashboard

## Step 5: Share!
Copy the frontend public URL and share with anyone:
Example: https://sdlc-docgen.railway.app

---

## Troubleshooting

**If services won't connect:**
- Check Railway logs (click service → Logs)
- Verify environment variables are set
- Ensure DATABASE_URL matches PostgreSQL addon credentials

**If you see connection errors:**
- Add Railway PostgreSQL addon variables to backend
- Restart services

**For LLM features:**
- LLM (Ollama) won't work on Railway free tier
- Set `LLM_EXTRACTION_ENABLED=false` (we already did this)
- Regex extractors will be used instead


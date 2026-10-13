# 🚀 Deployment Guide — Enterprise AI Operations Agent

Deploy the complete multi-agent system live in **under 15 minutes** on free/hobby tier cloud platforms.

---

## ⚡ Deployment Options Overview

| Target | Architecture | Setup Time | Monthly Cost | Best For |
|---|---|---|---|---|
| **Render** | Docker Web Service + PostgreSQL + Static Frontend | 10 mins | Free / $7 hobby | **Recommended for portfolio demos** |
| **Railway** | Docker Containers + Managed Postgres | 10 mins | $5 credit included | Easy 1-click Git deploy |
| **Docker Compose (Local)** | Full Lite Stack on your machine | 2 mins | $0 | Testing & local evaluation |

---

## Option 1: Deploy to Render (Recommended — 10 Minutes)

Render provides free PostgreSQL and Docker web services. This repository includes an Infrastructure-as-Code [render.yaml](file:///Users/saksham/Library/CloudStorage/OneDrive-UPES/projects/enterprise-ai-agent/render.yaml) blueprint.

### Prerequisites
- A free [Render account](https://render.com)
- A GitHub repository with this code
- At least one LLM API key ([OpenAI](https://platform.openai.com) or [Google Gemini](https://aistudio.google.com))

### Step-by-Step Instructions

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "feat: add lean deployable lite mode and demo seeds"
   git push origin main
   ```

2. **Launch via Render Blueprint**:
   - Log into the [Render Dashboard](https://dashboard.render.com).
   - Click **New +** in the top navigation and select **Blueprint**.
   - Connect your GitHub repository.
   - Render will parse `render.yaml` and provision:
     * `enterprise-ai-db` (Managed PostgreSQL 16)
     * `enterprise-ai-backend` (FastAPI with Docker runtime)
     * `enterprise-ai-frontend` (React + Vite static SPA)

3. **Configure Environment Secrets**:
   When prompted on the blueprint setup page, set your LLM API key:
   - `OPENAI_API_KEY`: `sk-...` *(or set `PRIMARY_PROVIDER=google` and `GEMINI_API_KEY`)*

4. **Run Initial Database Migration & Seed**:
   Once the backend service completes building and shows **Live**, open the Render backend shell tab (or SSH) and execute:
   ```bash
   python -m app.seed
   ```
   *This seeds the default organization, admin user, demo user, 3 sample enterprise documents, ChromaDB embeddings, sample chat histories, and pending human approvals.*

5. **Visit Your Live Application**:
   Navigate to the URL provided by `enterprise-ai-frontend` (e.g. `https://enterprise-ai-frontend.onrender.com`).
   - Click **👑 Admin** or **👤 Demo User** on the login page for 1-click authentication!

---

## Option 2: Deploy with Docker Compose Lite (Local / VPS — 2 Minutes)

Run the minimal, lean stack using [docker-compose.lite.yml](file:///Users/saksham/Library/CloudStorage/OneDrive-UPES/projects/enterprise-ai-agent/docker-compose.lite.yml):

### 1. Configure Environment
```bash
cp .env.example.lite .env
```
Edit `.env` and add your `OPENAI_API_KEY` or `GEMINI_API_KEY`.

### 2. Launch the Lite Cluster
```bash
docker compose -f docker-compose.lite.yml up --build -d
```
This starts:
- **FastAPI Backend**: `http://localhost:8000`
- **React Frontend**: `http://localhost:3000`
- **PostgreSQL Database**: `localhost:5432`
- **ChromaDB Vector Store**: `localhost:8001`
*(Heavy services like Redis, Celery, Neo4j, and Jaeger are automatically bypassed in lite mode).*

### 3. Seed Database
```bash
docker compose -f docker-compose.lite.yml exec backend python -m app.seed
```

### 4. Verify System Health
Visit `http://localhost:8000/readiness`:
```json
{
  "status": "ready",
  "mode": "lite",
  "demo_mode": true,
  "dependencies": {
    "postgresql": "connected",
    "chromadb": "connected",
    "redis": "disabled (lite mode)",
    "celery": "disabled (lite mode)",
    "neo4j": "disabled (lite mode)",
    "jaeger_tracing": "disabled (lite mode)"
  }
}
```

---

## Option 3: Deploy on Railway

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   railway login
   ```
2. Initialize project:
   ```bash
   railway init
   ```
3. Add a PostgreSQL plugin from the Railway dashboard.
4. Deploy the backend:
   ```bash
   railway up
   ```
5. Set environment variables in Railway dashboard:
   - `LITE_MODE=true`
   - `DEMO_MODE=true`
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   - `OPENAI_API_KEY=your_key`

---

## 🔒 Safety & Rate Limiting in Live Demo Mode

When `DEMO_MODE=true` is enabled:
- **Per-IP Rate Limiting**: Max 30 requests per 60 seconds per IP address (returns HTTP 429 if exceeded).
- **Daily Token Budget**: Automatically throttles chat completions if 100,000 tokens are consumed in a single day, preventing unexpected LLM bills.
- **SQL Agent Guardrails**: Write queries (UPDATE, DELETE, DROP) are automatically intercepted and converted into Human-in-the-Loop approvals rather than executing directly against production tables.

---

## 🔑 Pre-Seeded Demo Credentials

The database seed provides two accounts:

| Role | Email | Password | Permissions |
|---|---|---|---|
| **Admin** | `admin@enterprise-ai.local` | `admin123!` | Full system access, review approvals, manage users & settings |
| **Demo User** | `demo@enterprise-ai.local` | `demo123!` | Chat with agents, search documents, trigger SQL queries |

*Note: On the login page, you can use the **1-Click Demo Login** buttons to automatically sign in without typing credentials.*

---

## 🧪 2-Minute Recruiter Evaluation Script

Once deployed, you can demonstrate the full multi-agent architecture in 2 minutes:

1. **Multi-Agent Routing (Supervisor)**:
   - Ask: *"What is our remote work equipment budget and how do I submit receipts?"*
   - Observe: Supervisor routes to **RAG Agent**, retrieves chunks from `employee_handbook_2024.txt`, and cites the $500 stipend and 60-day policy window.
2. **Natural Language to SQL**:
   - Ask: *"How many users and organizations are in the system?"*
   - Observe: Supervisor routes to **SQL Agent**, generates `SELECT COUNT(...) FROM users`, executes safely, and prints a formatted markdown table.
3. **Human Approval Workflow (Safety)**:
   - Ask: *"Delete all inactive users from the database."*
   - Observe: SQL Agent detects a destructive `DELETE` operation, blocks direct execution, and creates an approval request.
   - Navigate to the **Approvals** tab in the sidebar as Admin to view the pending approval card!

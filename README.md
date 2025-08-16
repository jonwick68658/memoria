# memoria
AI Memory SDK
# Memoria – Hybrid Memory SDK + Gateway

Memoria gives LLM apps durable, per‑user memory with hybrid retrieval (vector + lexical + recency), rolling summaries, and pattern insights — while still letting models use general knowledge. It’s production-ready and runs as a single container: FastAPI + PostgreSQL (pgvector).

## Quick start

```bash
git clone https://github.com/jonwick68658/memoria
cd memoria
cp .env.sample .env  # fill in keys and config
docker compose up -d
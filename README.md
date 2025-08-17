# Memoria
AI Memory SDK
# Memoria – Hybrid Memory SDK + Gateway

Memoria gives LLM apps durable, per‑user memory with hybrid retrieval (vector + lexical + recency), rolling summaries, and pattern insights — while still letting models use general knowledge. It’s production-ready and runs as a single container: FastAPI + PostgreSQL (pgvector).

## Quick start

# Memoria

Memoria is a lightweight memory system for LLMs, designed to provide long-term memory, insights, and retrieval capabilities for chat-based applications. It supports OpenAI and OpenRouter integrations and is designed to be easily deployed and integrated into your services.

## Features
- Long-term memory storage and retrieval
- Insight generation from conversations
- Support for OpenAI and OpenRouter APIs
- Easy-to-use REST API

## Getting Started

### Prerequisites
- Docker and Docker Compose installed
- PostgreSQL with `pgvector` extension enabled
- OpenAI or OpenRouter API key

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/jonwick68658/memoria.git
   cd memoria

```bash
git clone https://github.com/jonwick68658/memoria
cd memoria
cp .env.example .env  # fill in keys and config
docker compose up -d


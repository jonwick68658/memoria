# Dependency Resolution Plan: Phase 1

This document outlines the proposed core dependencies for the Memoria application. The goal is to create a stable runtime environment by separating core logic from development, testing, and CI/CD tooling.

## Proposed `core-requirements.txt`

The following packages have been identified as essential for the application to run. All development, testing, and documentation packages have been excluded.

```
# Web Framework & Server
fastapi==0.104.1
uvicorn==0.24.0
gunicorn==22.0.0
python-multipart==0.0.6
aiohttp==3.9.5
websockets==12.0
sse-starlette==1.6.5
httptools==0.6.1
uvloop==0.19.0

# Data & Database
sqlalchemy==2.0.23
alembic==1.16.0
psycopg2-binary==2.9.9
redis==5.0.1
numpy==1.26.4
pandas==2.2.2

# AI & LLM Orchestration
openai==1.40.0
anthropic==0.30.0
tiktoken==0.5.2
transformers==4.41.0
torch==2.3.1
sentence-transformers==2.7.0
langchain==0.1.0
langchain-openai==0.0.1
langchain-anthropic==0.1.0
langchain-community==0.0.10

# Vector Stores
faiss-cpu==1.7.4
chromadb==0.4.24
weaviate-client==3.26.0
qdrant-client==1.9.0
pinecone-client==3.2.1

# Cloud & Object Storage
boto3==1.34.141
azure-storage-blob==12.20.0
google-cloud-storage==2.16.0

# Security (Runtime)
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
cryptography==42.0.8
pycryptodome==3.19.0
bcrypt==4.1.2
argon2-cffi==23.1.0

# Monitoring & Logging
prometheus-client==0.19.0
structlog==23.2.0
sentry-sdk==1.45.1
datadog==0.48.0
newrelic==9.2.0
python-json-logger==2.0.6
rich==13.7.1

# Async & Scheduling
celery==5.4.0
celery[redis]==5.4.0
flower==2.0.1
asyncio-mqtt==0.16.2
schedule==1.2.0
apscheduler==3.10.4

# CLI & Utilities
python-dotenv==1.0.0
httpx==0.26.0
requests==2.32.3
jinja2==3.1.4
```

## Next Steps

1.  Review and approve the proposed `core-requirements.txt`.
2.  I will then proceed to step 1.3: Generate a dependency tree for these core packages to visualize their interdependencies and identify any remaining conflicts.
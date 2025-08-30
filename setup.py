#!/usr/bin/env python3
"""
Setup script for Memoria - AI Memory System
"""

from setuptools import setup, find_packages
import os
import re

def read_version():
    """Read version from __init__.py"""
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, 'src', 'memoria', '__init__.py'), 'r') as f:
        content = f.read()
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content, re.M)
        if version_match:
            return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

def read_requirements(filename):
    """Read requirements from file."""
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def read_long_description():
    """Read long description from README."""
    with open('README.md', 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name="memoria-ai",
    version=read_version(),
    author="Memoria Team",
    author_email="team@memoria.ai",
    description="AI-powered memory system for intelligent conversations",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/jonwick68658/memoria",
    project_urls={
        "Documentation": "https://docs.memoria.ai",
        "Source": "https://github.com/jonwick68658/memoria",
        "Tracker": "https://github.com/jonwick68658/memoria/issues",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Database",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.5.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.12.0",
        "redis>=5.0.0",
        "celery>=5.3.0",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "python-dotenv>=1.0.0",
        "httpx>=0.25.0",
        "openai>=1.3.0",
        "anthropic>=0.7.0",
        "tiktoken>=0.5.0",
        "sentence-transformers>=2.2.0",
        "faiss-cpu>=1.7.0",
        "numpy>=1.24.0",
        "langchain>=0.0.350",
        "langchain-openai>=0.0.2",
        "langchain-anthropic>=0.1.0",
        "chromadb>=0.4.0",
        "structlog>=23.2.0",
        "prometheus-client>=0.19.0",
        "cryptography>=41.0.0",
        "bcrypt>=4.1.0",
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "websockets>=12.0",
        "sse-starlette>=1.6.0",
        "schedule>=1.2.0",
        "typer>=0.9.0",
        "click>=8.1.0",
        "jinja2>=3.1.0",
        "psycopg[binary]>=3.1.0",
        "pgvector>=0.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "mypy>=1.7.0",
            "pre-commit>=3.5.0",
            "factory-boy>=3.3.0",
            "faker>=20.0.0",
            "freezegun>=1.3.0",
            "responses>=0.24.0",
            "pytest-mock>=3.12.0",
            "coverage>=7.3.0",
            "bandit>=1.7.0",
            "safety>=2.3.0",
            "twine>=4.0.0",
            "wheel>=0.42.0",
            "build>=1.0.0",
        ],
        "postgres": ["psycopg2-binary>=2.9.0"],
        "mysql": ["PyMySQL>=1.1.0"],
        "sqlite": [],
        "cloud": [
            "boto3>=1.34.0",
            "azure-storage-blob>=12.19.0",
            "google-cloud-storage>=2.10.0",
        ],
        "monitoring": [
            "sentry-sdk>=1.38.0",
            "datadog>=0.47.0",
            "newrelic>=9.2.0",
        ],
        "vector-stores": [
            "weaviate-client>=3.25.0",
            "qdrant-client>=1.6.0",
            "pinecone-client>=2.2.0",
        ],
        "all": [
            "psycopg2-binary>=2.9.0",
            "boto3>=1.34.0",
            "azure-storage-blob>=12.19.0",
            "google-cloud-storage>=2.10.0",
            "sentry-sdk>=1.38.0",
            "datadog>=0.47.0",
            "newrelic>=9.2.0",
            "weaviate-client>=3.25.0",
            "qdrant-client>=1.6.0",
            "pinecone-client>=2.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "memoria=memoria.cli:main",
            "memoria-server=memoria.server:main",
            "memoria-migrate=memoria.migrations:main",
        ],
    },
    include_package_data=True,
    package_data={
        "memoria": [
            "templates/*.html",
            "static/css/*.css",
            "static/js/*.js",
            "static/img/*",
            "migrations/*.py",
            "config/*.yaml",
            "config/*.json",
        ],
    },
    zip_safe=False,
)

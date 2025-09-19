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
    name="memoria",
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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Database",
    ],
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.7.0",
        "httpx>=0.26.0",
        "openai>=1.40.0",
        "orjson>=3.9.10",
        "tenacity>=8.2.0",
        "psycopg[binary]>=3.2.0",
        "pgvector>=0.2.5",
        "redis>=5.0.0",
        "celery>=5.4.0",
        "sse-starlette>=1.6.0",
        "prometheus-client>=0.19.0",
        "python-dotenv>=1.0.0",
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

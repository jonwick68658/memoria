-- Initialize database for Memoria application
-- This script runs when the PostgreSQL container starts

-- Create the database if it doesn't exist
CREATE DATABASE memoria_db WITH OWNER = memoria;

-- Connect to the database
\c memoria_db

-- Create the memoria user if it doesn't exist
CREATE USER memoria WITH PASSWORD 'memoria123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE memoria_db TO memoria;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
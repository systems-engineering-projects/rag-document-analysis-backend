# RAG Document Analysis Backend

FastAPI-based RAG backend for document ingestion, embeddings, pgvector search, and contextual Q&A workflows.

The system ingests report documents, generates embeddings, stores them in **Postgres with pgvector**, and retrieves relevant context to generate suggested report language using an LLM.

Originally built to generate suggested verbiage for storm damage reports by analyzing prior case documentation.

---

# System Overview

This project demonstrates an end-to-end **RAG architecture** combining:

- document ingestion and chunking  
- embedding generation  
- vector similarity search  
- LLM-assisted response generation  
- stateless API design suitable for deployment environments  

The backend can run using either **OpenAI APIs** or **local models via Ollama**.

---

# Key Features

## Document Ingestion

- Upload PDF or text content  
- Documents are chunked and embedded  
- Embeddings stored in Postgres using pgvector  

## Vector Retrieval

- Semantic similarity search over stored document chunks  
- Relevant context retrieved for each query  

## LLM Response Generation

- Generates structured suggested text using retrieved context  
- Supports OpenAI or local Ollama models  

## Query Interface

- Ask questions about previously ingested documents  
- Returns contextual responses based on similar prior content  

## Optional Web UI

- Lightweight interface for document ingestion and querying  
- Useful for testing and demonstrations  

---

# Architecture

Typical request flow:

1. Document is uploaded or text is ingested  
2. Content is chunked and embedded  
3. Embeddings stored in Postgres using pgvector  
4. User submits a query  
5. Similar document chunks retrieved via vector search  
6. LLM generates contextual response using retrieved context  

---

# Technology Stack

| Layer | Technology |
|------|------------|
| API | FastAPI |
| Database | PostgreSQL |
| Vector Store | pgvector |
| Embeddings | OpenAI or Ollama |
| LLM | OpenAI or Ollama |
| Language | Python |

---

## Deployment Model

The service is designed as a **containerized backend API** suitable for local development or deployment environments.

The repository includes Docker configuration that runs:

- FastAPI application
- PostgreSQL with pgvector enabled

Environment configuration follows **12-factor application principles** and is managed through environment variables.

The only required configuration is an API key for the LLM provider.

---

## Running the System

The application can be started using Docker.

### 1. Clone the repository
git clone https://github.com/systems-engineering-projects/rag-document-analysis-backend.git
cd rag-document-analysis-backend

---

## Running the System

The application can be started using Docker.

### 1. Clone the repository
git clone https://github.com/systems-engineering-projects/rag-document-analysis-backend.git
cd rag-document-analysis-backend

### 2. Configure environment variables
Create a .env file:
OPENAI_API_KEY=your_key_here

### 3. Start the system
docker compose up --build

This will start:
- FastAPI backend
- PostgreSQL database with pgvector
- embedding + retrieval pipeline

The API will be available at:
- http://localhost:8000
- Optional: Local Models with Ollama
- Instead of OpenAI, the system can use local models.

Install Ollama and pull the required models:
ollama pull nomic-embed-text
ollama pull llama3.1:8b

Then configure the application to use the Ollama provider.

---

# Purpose

This project demonstrates practical engineering patterns for building AI-enabled backend systems:

- Retrieval-Augmented Generation (RAG)
- vector database integration with pgvector
- containerized AI service deployment
- configurable inference providers (OpenAI or local models)

---

# Future Extensions

Potential improvements include:

- automated document ingestion pipelines  
- additional vector search optimizations  
- streaming responses  
- expanded document source integrations




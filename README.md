# Enterprise Event-Driven Claims Triage Platform

An enterprise multi-agent automation platform that processes e-commerce refund claims asynchronously using vector Retrieval-Augmented Generation (RAG), risk scoring heuristics, and automated payment gateway integrations.

## Architecture
- **API Gateway**: FastAPI (`app/main.py`)
- **Background Worker**: Celery + SQLite Broker (`app/celery_worker.py`)
- **Vector RAG Engine**: Qdrant Vector DB (`app/rag_service.py`)
- **Agents**: Policy Agent & Fraud Risk Agent (`app/agents/`)
- **Tools**: Stripe Sandbox Refund Executor (`app/payment_tool.py`), OCR Receipt Extractor (`app/ocr_tool.py`)

## Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
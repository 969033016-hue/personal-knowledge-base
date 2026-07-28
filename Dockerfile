FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KNOWLEDGE_STORAGE_BACKEND=tos \
    KNOWLEDGE_DB_PATH=/tmp/knowledge.db

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY knowledge_mcp ./knowledge_mcp
COPY data/bootstrap_categories.json ./data/bootstrap_categories.json

EXPOSE 8000

CMD ["uvicorn", "knowledge_mcp.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

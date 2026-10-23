FROM python:3.11-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace/services/fastapi
COPY requirements.txt ./
COPY app/requirements.txt ./app/requirements.txt
COPY rag/requirements.txt ./rag/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY rag/ ./rag/
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]

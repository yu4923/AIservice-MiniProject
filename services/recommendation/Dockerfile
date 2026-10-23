FROM python:3.11-slim
WORKDIR /workspace/services/recommendation
COPY requirements.txt ./
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]

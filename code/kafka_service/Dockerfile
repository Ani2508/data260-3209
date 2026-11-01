# HW8 image for the Kafka worker and the FastAPI wrapper
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "kafka-python>=2.2" fastapi "uvicorn[standard]" tzdata
COPY *.py ./
ENV PYTHONUNBUFFERED=1

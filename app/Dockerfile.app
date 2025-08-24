# Dockerfile.app
FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the application port and Prometheus metrics port
EXPOSE 5000
EXPOSE 8000

CMD ["python", "main.py"]

# Azure Container Apps runs linux/amd64 only. Build with
#   docker buildx build --platform linux/amd64 ...
# On an arm64 machine a plain `docker build` pushes successfully and then
# crash-loops with an exec format error.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY templates ./templates

# Run unprivileged: nothing here needs root, and the image holds no credentials
# because authentication is entirely through the managed identity at runtime.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

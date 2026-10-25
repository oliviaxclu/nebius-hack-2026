FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY prime ./prime
RUN pip install --no-cache-dir ".[web]"
RUN useradd -m app && mkdir -p /tmp/prime && chown app /tmp/prime
USER app
# Serves ONLY the synthetic patient; visitor sessions live in memory + /tmp (lost on restart by design).
ENV PRIME_HOME=/tmp/prime PORT=8080
EXPOSE 8080
# One worker: visitor sessions are held in process memory.
CMD ["sh", "-c", "uvicorn prime.web:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 1"]

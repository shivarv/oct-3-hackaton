FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv && useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .
USER app
EXPOSE 8000
CMD ["uvicorn", "secaudit.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

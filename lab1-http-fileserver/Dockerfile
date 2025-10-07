FROM python:3.11-slim
WORKDIR /app
COPY src/ /app/
# Non-root for good measure
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
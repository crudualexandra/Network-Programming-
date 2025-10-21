# File: Dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY src/ /app/
EXPOSE 8000
# default command (compose overrides with workers/delay)
CMD ["python","server.py","/app/site","--host","0.0.0.0","--port","8000"]
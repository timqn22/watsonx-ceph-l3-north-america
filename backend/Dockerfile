FROM registry.redhat.io/ubi9/python-311-minimal:latest

WORKDIR /app

# Install dependencies as root, then switch to a non-root user.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Never run as root in production.
USER 1001

EXPOSE 8000

# Bind to localhost only — a reverse proxy (nginx, k8s Service) handles
# external exposure. 0.0.0.0 is only appropriate behind a known-trusted proxy.
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]

FROM python:3.11-slim

# Install mdbtools for reading Microsoft Access .mdb files
RUN apt-get update && \
    apt-get install -y --no-install-recommends mdbtools && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY sql/ sql/

CMD ["python", "src/pipeline.py"]

FROM python:3.11-slim

# Install mdbtools for reading Microsoft Access .mdb files
# and curl for downloading NTSB data
RUN apt-get update && \
    apt-get install -y --no-install-recommends mdbtools curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY sql/ sql/

CMD ["python", "src/pipeline.py"]

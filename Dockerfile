FROM python:3.11-slim

LABEL maintainer="league-infrastructure" \
      description="Partner website mirroring system"

WORKDIR /app

# System libraries required by Scrapy / lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Create the output directory (will be overridden by a volume mount in practice)
RUN mkdir -p data/mirrors

# Default: mirror all partners
ENTRYPOINT ["python", "run_mirrors.py"]

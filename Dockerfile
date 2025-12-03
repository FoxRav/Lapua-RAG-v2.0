FROM python:3.11-slim

WORKDIR /app

# System dependencies for building Python packages (e.g. torch, FlagEmbedding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install project with extra dependencies needed for embeddings
RUN pip install --upgrade pip && pip install .[embeddings]

# Default port; Railway will override PORT env, but we expose 8000 for clarity
ENV PORT=8000
EXPOSE 8000

# Start FastAPI app
CMD ["uvicorn", "apps.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]



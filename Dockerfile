# Use an official Python runtime as a parent image
FROM python:3.9-slim

WORKDIR /app

# --- Cache Locations ---
ENV PIP_CACHE_DIR=/app/.cache/pip
ENV TORCH_HOME=/app/.cache/torch
ENV HF_HOME=/app/.cache/huggingface
ENV XDG_CACHE_HOME=/app/.cache

# Install ffmpeg, a system-level dependency for Whisper
RUN apt-get update && apt-get install -y ffmpeg

# Install dependencies
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt


# Copy backend and frontend
COPY ./backend /app/backend
COPY ./index.html /app/
COPY ./script.js /app/
COPY ./style.css /app/

# Ensure cache exists and preload Whisper model
RUN mkdir -p /app/.cache && \
    python -c "import whisper; whisper.load_model('base')"

# Run the app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]

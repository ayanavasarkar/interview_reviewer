# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# --- NEW LINE ---
# Set a writable cache directory to avoid permission errors
ENV HF_HOME=/app/.cache

# --- Backend Setup ---
# Copy the requirements file from the backend folder
COPY ./backend/requirements.txt /app/requirements.txt

# Install the Python dependencies
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the entire backend directory into the container
COPY ./backend /app/backend

# --- Frontend Setup ---
# Copy the frontend files directly into the working directory
COPY ./index.html /app/
COPY ./script.js /app/
COPY ./style.css /app/

# --- Run Command ---
# Command to run the app from the 'main' module inside the 'backend' directory
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
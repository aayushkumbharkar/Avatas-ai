# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Add any system dependencies here if needed (e.g., build-essential for some Python packages)
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app /code/app

# Expose the port the app runs on
# This will be overridden by .env file or environment variable if Uvicorn is started with --port $PORT
EXPOSE 8000

# Command to run the application
# The default host is 0.0.0.0, which is what we want for Docker
# The port can be set via the PORT environment variable (loaded from .env by uvicorn if python-dotenv is used correctly)
# or directly in the command if preferred.
# Using environment variable for port is more flexible.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

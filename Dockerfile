# Use a lightweight official Python image
FROM python:3.10-slim

# Avoid writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies if any are needed (none for pure python/fastapi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
ENV HOME=/home/user
WORKDIR $HOME/app

# Copy application files and grant ownership to the user
COPY --chown=user:1000 . $HOME/app

# Use the non-root user
USER user

# Set production environment variables
ENV PORT=7860
ENV PROD=true

# Expose port 7860
EXPOSE 7860

# Run the FastAPI app
CMD ["python", "-m", "backend.main"]

# Use official Python image as a base
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code into the container
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 5001

# Use Gunicorn to run the Flask application
CMD ["gunicorn", "--workers", "3", "--timeout", "300", "--bind", "0.0.0.0:5001", "app:app"]
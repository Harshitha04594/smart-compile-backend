# Use the official Python image as the base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the Python requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend files (app.py) into the container
COPY . .

# Expose the port that Flask runs on (Cloud Run requires 8080 by default)
EXPOSE 8080

# Command to run the application when the container starts
# We use Gunicorn, a production-grade server, instead of the Flask development server
# The --bind 0.0.0.0:8080 argument is critical for cloud platforms
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
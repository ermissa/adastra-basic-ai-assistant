FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install dependencies
COPY ./requirements-docker.txt .
RUN pip install -r requirements-docker.txt

# Copy project files
COPY . /app

# Expose port (change if needed)
EXPOSE 8000

# Run migrations and start server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
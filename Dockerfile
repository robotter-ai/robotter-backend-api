# Start from a base image with Miniconda installed
FROM continuumio/miniconda3

# Install system dependencies
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0 python3-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /backend-api

# Copy only the environment.yml file first
COPY environment.yml .

# Create the environment from the environment.yml file
RUN conda env create -f environment.yml

# Make RUN commands use the new environment
SHELL ["conda", "run", "-n", "backend-api", "/bin/bash", "-c"]

# Copy the rest of the application code
COPY . .

RUN mkdir -p /backend-api/bots/credentials

# The code to run when container is started
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "backend-api", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

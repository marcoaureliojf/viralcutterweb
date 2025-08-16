# Use an official NVIDIA CUDA base image with Python pre-installed
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# Set environment variables to prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies, including git, ffmpeg, curl (for Node.js setup)
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    fonts-liberation \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
    
    
# Install a modern version of Node.js (e.g., LTS version 20)
# Using the official NodeSource repository is recommended over apt's default
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# --- Install Python Dependencies (Leveraging Docker Cache) ---
# First, copy only the requirements file
COPY ./requirements.txt /app/requirements.txt

# Then, install the dependencies. This layer will only be re-built if requirements.txt changes.
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# --- Install Node.js Dependencies (Leveraging Docker Cache) ---
# First, copy only the package.json and package-lock.json files
# COPY ./package*.json ./

# Then, install the dependencies. This layer will only be re-built if package files change.
RUN npm install

# --- Add Application Code and Build Frontend Assets ---
# Now copy the rest of the application source code


# Run the Tailwind CSS build command. This generates the final /static/css/output.css
# This must be a RUN command, as it's part of the image build process.
RUN npm run build-css

# Expose the port the FastAPI app will run on
EXPOSE 8000

# The command to run the application using Uvicorn
# --host 0.0.0.0 makes it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
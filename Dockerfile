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
    wget \
    intel-media-va-driver-non-free \
    && rm -rf /var/lib/apt/lists/*

# Install a modern version of Node.js (LTS v20)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# --- Install Python Dependencies (Leveraging Docker Cache) ---
# First, copy only the requirements file
COPY ./requirements.txt /app/requirements.txt

# Upgrade pip and install requirements
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

# --- Install PyCaps from GitHub ---
RUN pip3 install --no-cache-dir git+https://github.com/francozanardi/pycaps.git 

# --- Install Playwright and Chromium ---
RUN pip3 install --no-cache-dir playwright \
    && playwright install --with-deps chromium

# Copy all application code into the container
COPY . .

# --- Install Node.js Dependencies (Leveraging Docker Cache) ---
# Uncomment if you have package.json in repo
COPY ./package*.json ./
RUN npm install

# Build Tailwind CSS
RUN npm run build-css

# Expose the port the FastAPI app will run on
EXPOSE 8000

# Default command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

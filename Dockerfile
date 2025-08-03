FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV NVM_DIR=/root/.nvm

# Install system dependencies needed for your requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        ca-certificates \
        gnupg \
        build-essential \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpq-dev \
        python3-dev \
        git \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js v18 using NVM
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && \
    . "$NVM_DIR/nvm.sh" && \
    nvm install 18 && \
    nvm alias default 18 && \
    npm install -g npm && \
    echo ". $NVM_DIR/nvm.sh" >> /root/.bashrc

# Set working directory
WORKDIR /app

# Copy files
COPY . /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir -U pip setuptools wheel && \
    pip3 install --no-cache-dir -U -r requirements.txt

# Ensure start script is executable
RUN chmod +x start

# Final entrypoint
CMD ["/bin/bash", "-c", "source ~/.bashrc && bash start"]

# Final CMD
CMD ["/bin/bash", "-c", "source ~/.bashrc && bash start"]

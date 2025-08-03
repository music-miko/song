# Use Python slim base
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV NVM_DIR=/root/.nvm

# Install required system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        ca-certificates \
        gnupg \
        build-essential \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js v18 via NVM
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && \
    . "$NVM_DIR/nvm.sh" && \
    nvm install 18 && \
    nvm alias default 18 && \
    npm install -g npm && \
    echo ". $NVM_DIR/nvm.sh" >> /root/.bashrc

# Set working directory
WORKDIR /app

# Copy all files
COPY . /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir -U -r requirements.txt

# Make start script executable
RUN chmod +x start

# Final CMD
CMD ["/bin/bash", "-c", "source ~/.bashrc && bash start"]

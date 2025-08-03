FROM nikolaik/python-nodejs:python3.10-nodejs19

# Install ffmpeg
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js v18 via NVM
ENV NVM_DIR=/root/.nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && \
    . "$NVM_DIR/nvm.sh" && \
    nvm install 18 && \
    nvm alias default 18 && \
    npm install -g npm && \
    echo ". $NVM_DIR/nvm.sh" >> /root/.bashrc

# Set working directory and copy files
COPY . /app/
WORKDIR /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir -U -r requirements.txt

# Ensure start is executable
RUN chmod +x start

# Run the bot
CMD ["/bin/bash", "-c", "source ~/.bashrc && bash start"]

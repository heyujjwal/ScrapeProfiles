# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Download and install a matching version of Chrome and ChromeDriver
RUN LAST_KNOWN_GOOD_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" && \
    CHROME_URL=$(wget -qO- ${LAST_KNOWN_GOOD_URL} | jq -r '.channels.Stable.downloads.chrome[] | select(.platform=="linux64").url') && \
    wget -O /tmp/chrome-linux64.zip ${CHROME_URL} && \
    unzip /tmp/chrome-linux64.zip -d /opt/ && \
    ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome && \
    rm /tmp/chrome-linux64.zip && \
    \
    DRIVER_URL=$(wget -qO- ${LAST_KNOWN_GOOD_URL} | jq -r '.channels.Stable.downloads.chromedriver[] | select(.platform=="linux64").url') && \
    wget -O /tmp/chromedriver-linux64.zip ${DRIVER_URL} && \
    unzip /tmp/chromedriver-linux64.zip -d /opt/ && \
    ln -s /opt/chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    rm /tmp/chromedriver-linux64.zip

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 10000

# Command to run the app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120", "app:app"]
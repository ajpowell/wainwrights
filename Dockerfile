FROM python:3.9-slim

WORKDIR /home/wainwrights

# Install dependencies first so the application image stays reproducible.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user to run the server and a writable data directory for the user DB.
RUN adduser --gecos "" --disabled-password wainwrights \
    && mkdir -p /data \
    && chown -R wainwrights:wainwrights /home/wainwrights /data

ENV WAINWRIGHTS_USER_DB_PATH=/data/wainwrights_users.db

# Copy the application sources and static assets.
COPY ./static/ ./static/
COPY server.py .
COPY wainwrights.db .

VOLUME ["/data"]
USER wainwrights

EXPOSE 5000

# Run the Flask app
CMD ["python", "server.py"]

# Build with:
# podman build -t wainwrights:latest . 
#
# Run interactively with:
# podman run -it --rm -p 5000:5000 --name wainwrights wainwrights:latest

# Run as a daemon with:
# podman run -d --rm -p 5000:5000 --name wainwrights wainwrights:latest

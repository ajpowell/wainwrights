FROM python:3.13-slim

# Install dependencies first so the application image stays reproducible.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user to run the server and a writable data directory for the user DB.
RUN adduser --home /home/wainwrights --disabled-password --gecos "" wainwrights \
    && mkdir -p /data \
    && chown -R wainwrights:wainwrights /home/wainwrights /data

WORKDIR /home/wainwrights

ENV WAINWRIGHTS_USER_DB_PATH=/data/wainwrights_users.db
ENV WEB_CONCURRENCY=1
ENV GUNICORN_THREADS=2
ENV GUNICORN_TIMEOUT=60

# Copy the application sources and static assets.
COPY ./static/ ./static/
COPY server.py .
COPY wainwrights.db .

VOLUME ["/data"]
USER wainwrights

EXPOSE 5000

# Run the Flask app behind Gunicorn with a minimal worker footprint.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:5000 --workers ${WEB_CONCURRENCY:-1} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-60} server:app"]

# Build with:
# podman build -t wainwrights:latest . 
#
# Run interactively with:
# podman run -it --rm -p 5000:5000 --name wainwrights wainwrights:latest

# Run as a daemon with:
# podman run -d --rm -p 5000:5000 --name wainwrights wainwrights:latest

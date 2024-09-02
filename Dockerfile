FROM python:3.9-slim

# Create a non-root user to own the files and run our server
RUN adduser wainwrights
USER wainwrights
WORKDIR /home/wainwrights

# Copy the static website
# Use the .dockerignore file to control what ends up inside the image!
COPY ./static/ ./static/
COPY requirements.txt .
COPY server.py .
COPY wainwrights.db .

RUN pip install -r requirements.txt

EXPOSE 5000

# Run BusyBox httpd
CMD ["python", "server.py"]

# Build with:
# podman build -t wainwrights:latest . 
#
# Run interactively with:
# podman run -it --rm -p 5000:5000 --name wainwrights wainwrights:latest

# Run as a daemon with:
# podman run -d --rm -p 5000:5000 --name wainwrights wainwrights:latest
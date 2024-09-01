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
# Run with:
# podman run -it --rm -p 8080:5000 wainwrights:latest
# wainwrights

Mapping Wainwrights on openstreetmap using leafletjs

example.html provides a basic page that displays a map (centered on Scarfell Pike) - green tick marker indicates Wainwrights that have been climbed.

![](./images/example.html.png)

The marker data is supplied from server.py microservice with a sqlite DB backend.

## Usage - casual usage:

 - From a terminal, start venv:
    
    `python3 -m venv .venv`

 - Activate the venv:

    `. ./.venv/bin/activate`

 - Install the requirements:
 
    `pip install -r requirements.txt`

 - Start the microservice (wainwrights api):
 
    `python server.py`

 - Open example.html in a browser

## Future plans/intentions:

- Use better DB (MySQL or PostgreSQL) - will support better throughput
- Containerise the microservice with a suitable server process for Flask
- Extend the database of Wainwrights to cover more hills in UK
- Put 'climbed' details in a separate table
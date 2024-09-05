#!/usr/bin/env python
# encoding: utf-8
# import json
from flask import Flask, jsonify, request
import sqlite3
# import json
from datetime import datetime


ver = '0.1.1'

port = 5000

debug = False

server_starttime = datetime.now()

app = Flask(__name__, static_url_path='/static')


# Helper function to return a response with status code and CORS headers
def prepare_response(res_object, status_code):
    response = jsonify(res_object)
    # response = res_object
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST')

    # print(response)
    return response, status_code


@app.route('/', methods=['GET'])
def mainpage():
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    print('Your IP address is: {}'.format(ip_addr))

    with open('./static/example.html', 'r') as fd:
        data = fd.read()

    return data, 200


@app.route('/test/', methods=['GET'])
def test():
    # api query to check api server is running
    data = 'ACK'

    return prepare_response(data, 200)


@app.route('/version/', methods=['GET'])
def version():
    # api query to check api server is running
    data = {"version": ver}

    return prepare_response(data, 200)


@app.route('/stats/', methods=['GET'])
def stats():
    # api query to get statistics about the api server
    # TODO
    now = datetime.now()
    # Get uptime in human readable form
    td = now - server_starttime
    td_sec = td.seconds                                  # getting the seconds field of the timedelta
    hour_count, rem = divmod(td_sec, 3600)               # calculating the total hours
    minute_count, second_count = divmod(rem, 60)
    timedelta_str = 'Uptime: {} days, {} hours, {} minutes, {} seconds'.format(td.days, hour_count, minute_count, second_count)
    data = {
        "server_currenttime": now,
        "server_starttime": server_starttime,
        "server_uptime": timedelta_str,
        "server_version": ver
        }
    return prepare_response(data, 200)


@app.route('/climbed/', methods=['GET'])
def climbed():
    # Return all the wainwrights that have been climbed
    con = sqlite3.connect('wainwrights.db')
    con.row_factory = sqlite3.Row  # This enables column access by name: row['column_name']

    # Create a cursor object using the connection's "cursor" method
    cur = con.cursor()

    # Execute a SQL statement
    rows = cur.execute("SELECT * FROM wainwrights where climbed = 1;").fetchall()

    data = [dict(ix) for ix in rows]

    return prepare_response(data, 200)


@app.route('/wainwrights/', methods=['GET'])
def index():
    lat1 = request.args.get('lat1')
    lng1 = request.args.get('lng1')
    lat2 = request.args.get('lat2')
    lng2 = request.args.get('lng2')

    # print('northEast: lat:{} lng:{}'.format(lat1, lng1))
    # print('southWest: lat:{} lng:{}'.format(lat2, lng2))

    """return prepare_response(
                  (
                    #  [2359,"Scafell Pike",978.07,3209,54.454263,-3.211682,1],
                    #  [2360,"Scafell",963.9,3162,54.447498,-3.224731,0],
                    {'id': 2359, 'name': 'Scafell Pike', 'height_m': 978.07, 'height_ft': 3209, 'lat': 54.454263, 'lng': -3.211682, 'climbed': 1},
                    {'id': 2360, 'name': 'Scafell', 'height_m': 963.9, 'height_ft': 3162, 'lat': 54.447498, 'lng': -3.224731, 'climbed': 0},
                  ),
                  200
                  )"""

    con = sqlite3.connect('wainwrights.db')
    con.row_factory = sqlite3.Row  # This enables column access by name: row['column_name']

    # Create a cursor object using the connection's "cursor" method
    cur = con.cursor()

    # SELECT * FROM wainwrights
    #  WHERE lat BETWEEN 54.442438 AND 54.482348
    #    AND lng BETWEEN -3.304963 AND -3.201966;
    sql = 'SELECT * FROM wainwrights WHERE lat BETWEEN {} AND {} AND lng between {} and {};'.format(lat2, lat1, lng2, lng1)

    # print(sql)

    # Execute a SQL statement
    rows = cur.execute(sql).fetchall()

    data = [dict(ix) for ix in rows]

    return prepare_response(data, 200)


if __name__ == '__main__':
    print('')
    print('wainwrights api v{}'.format(ver))
    print('')

    # Run on all interfaces...
    app.run(debug=debug, host='0.0.0.0', port=port)

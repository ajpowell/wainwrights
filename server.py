#!/usr/bin/env python
# encoding: utf-8
from datetime import datetime, timedelta
import csv
import io
import os
from pathlib import Path
import logging
import sqlite3
import time

from flask import Flask, jsonify, render_template_string, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash


ver = '1.0.0'

port = 5000

debug = False

server_starttime = datetime.now()

app = Flask(__name__, static_url_path='/static')
app.secret_key = os.environ.get('WAINWRIGHTS_SECRET_KEY', 'wainwrights-local-dev-secret')
app.permanent_session_lifetime = timedelta(days=90)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
DB_PATH = BASE_DIR / 'wainwrights.db'
USER_DB_PATH = Path(os.environ.get('WAINWRIGHTS_USER_DB_PATH', str(BASE_DIR / 'wainwrights_users.db')))

logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)sZ %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)
logger = logging.getLogger('wainwrights')


def initialize_user_db():
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(USER_DB_PATH) as con:
        con.execute('PRAGMA foreign_keys = ON;')
        con.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            '''
        )
        con.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_climbs (
                user_id INTEGER NOT NULL,
                wainwright_id INTEGER NOT NULL,
                climbed INTEGER NOT NULL DEFAULT 1,
                climb_date TEXT,
                comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, wainwright_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            '''
        )


def current_user():
    user_id = session.get('user_id')
    username = session.get('username')
    if not user_id or not username:
        return None

    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            'SELECT id, username, created_at, updated_at FROM users WHERE id = ?;',
            (user_id,),
        ).fetchone()

    if row is None:
        session.clear()
        return None

    return dict(row)


def get_user_by_username(username):
    if not username:
        return None

    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            'SELECT id, username, created_at, updated_at FROM users WHERE username = ?;',
            (username,),
        ).fetchone()

    return dict(row) if row is not None else None


def get_base_wainwright_rows():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute('SELECT * FROM wainwrights ORDER BY id;').fetchall()
    return rows


def get_user_climb_map(user_id):
    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            '''
            SELECT wainwright_id, climb_date, comment
            FROM user_climbs
            WHERE user_id = ? AND climbed = 1;
            ''',
            (user_id,),
        ).fetchall()

    return {row['wainwright_id']: dict(row) for row in rows}


def get_user_climb_count(user_id):
    with sqlite3.connect(USER_DB_PATH) as con:
        count = con.execute(
            'SELECT COUNT(*) FROM user_climbs WHERE user_id = ? AND climbed = 1;',
            (user_id,),
        ).fetchone()[0]

    return count


def get_user_climb_rows(user_id):
    wainwright_names = {
        row['id']: row['name']
        for row in get_base_wainwright_rows()
    }

    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            '''
            SELECT wainwright_id, climbed, climb_date, comment, created_at, updated_at
            FROM user_climbs
            WHERE user_id = ? AND climbed = 1
            ORDER BY wainwright_id;
            ''',
            (user_id,),
        ).fetchall()

    exported_rows = []
    for row in rows:
        row_dict = dict(row)
        row_dict['wainwright_name'] = wainwright_names.get(row_dict['wainwright_id'], '')
        exported_rows.append(row_dict)

    return exported_rows


def parse_import_bool(value):
    text = str(value or '').strip().lower()
    if text in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if text in ('0', 'false', 'no', 'n', 'off', ''):
        return False
    return None


def normalize_optional_text(value):
    text = '' if value is None else str(value).strip()
    return text or None


def resolve_view_context():
    requested_username = (request.args.get('user') or '').strip() or None
    session_user = current_user()

    if requested_username:
        view_user = get_user_by_username(requested_username)
        if view_user is None:
            return {
                'requested_username': requested_username,
                'view_user': None,
                'view_exists': False,
                'can_edit': False,
                'session_user': session_user,
            }

        return {
            'requested_username': requested_username,
            'view_user': view_user,
            'view_exists': True,
            'can_edit': session_user is not None and session_user['username'] == view_user['username'],
            'session_user': session_user,
        }

    if session_user is not None:
        return {
            'requested_username': None,
            'view_user': session_user,
            'view_exists': True,
            'can_edit': True,
            'session_user': session_user,
        }

    return {
        'requested_username': None,
        'view_user': None,
        'view_exists': False,
        'can_edit': False,
        'session_user': None,
    }


def build_wainwright_payload(view_context=None):
    view_context = view_context or resolve_view_context()
    view_user = view_context['view_user']
    can_edit = view_context['can_edit']
    base_rows = get_base_wainwright_rows()
    climbed_map = get_user_climb_map(view_user['id']) if view_user else {}

    payload = []
    for row in base_rows:
        row_dict = dict(row)
        if view_user:
            user_climb = climbed_map.get(row_dict['id'])
            row_dict['climbed'] = 1 if user_climb else 0
            row_dict['climb_date'] = user_climb['climb_date'] if user_climb else None
            row_dict['comment'] = user_climb['comment'] if user_climb else ''
            row_dict['editable'] = can_edit
            row_dict['view_mode'] = 'user' if can_edit else 'shared'
        else:
            row_dict['editable'] = False
            row_dict['view_mode'] = 'readonly'
            row_dict['climb_date'] = None
            row_dict['comment'] = ''
        payload.append(row_dict)

    return payload


def iso_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


initialize_user_db()


# Helper function to return a response with status code and CORS headers
def prepare_response(res_object, status_code):
    response = jsonify(res_object)
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST')

    return response, status_code


@app.route('/', methods=['GET'])
def mainpage():
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    logger.info('mainpage request ip=%s', ip_addr)

    template_path = STATIC_DIR / 'wainwrights.html'
    with template_path.open('r', encoding='utf-8') as handle:
        template = handle.read()

    return render_template_string(
        template,
        app_base_path='/wainwrights/',
        asset_base_path=request.script_root or '/',
    )


@app.route('/assets/<path:filename>', methods=['GET'])
def assets(filename):
    return send_from_directory(STATIC_DIR, filename)


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


@app.route('/wainwrights/api/me', methods=['GET'])
@app.route('/api/me', methods=['GET'])
def api_me():
    user = current_user()
    if user is None:
        return prepare_response({"authenticated": False, "username": None}, 200)

    return prepare_response(
        {
            "authenticated": True,
            "username": user['username'],
            "user_id": user['id'],
        },
        200,
    )


@app.route('/wainwrights/api/login', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def api_login():
    payload = request.get_json(silent=True) or request.form or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''

    if not username or not password:
        return prepare_response({"error": "username and password are required"}, 400)

    if len(username) > 64:
        return prepare_response({"error": "username is too long"}, 400)

    now = iso_now()
    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            'SELECT id, username, password_hash FROM users WHERE username = ?;',
            (username,),
        ).fetchone()

        if row is None:
            password_hash = generate_password_hash(password)
            cur = con.execute(
                '''
                INSERT INTO users (username, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?);
                ''',
                (username, password_hash, now, now),
            )
            user_id = cur.lastrowid
            created = True
        else:
            if not check_password_hash(row['password_hash'], password):
                return prepare_response({"error": "invalid username or password"}, 401)
            user_id = row['id']
            created = False

    session.clear()
    session.permanent = True
    session['user_id'] = user_id
    session['username'] = username

    logger.info('login username=%s created=%s', username, created)

    return prepare_response(
        {
            "ok": True,
            "authenticated": True,
            "created": created,
            "username": username,
        },
        200,
    )


@app.route('/wainwrights/api/logout', methods=['POST'])
@app.route('/api/logout', methods=['POST'])
def api_logout():
    user = current_user()
    username = user['username'] if user else None
    session.clear()
    logger.info('logout username=%s', username)
    return prepare_response({"ok": True}, 200)


@app.route('/wainwrights/api/climbs/export', methods=['GET'])
@app.route('/api/climbs/export', methods=['GET'])
def export_climbs():
    user = current_user()
    if user is None:
        return prepare_response({"error": "login required"}, 401)

    rows = get_user_climb_rows(user['id'])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'wainwright_id',
        'wainwright_name',
        'climbed',
        'climb_date',
        'comment',
        'created_at',
        'updated_at',
    ])
    for row in rows:
        writer.writerow([
            row['wainwright_id'],
            row['wainwright_name'],
            row['climbed'],
            row['climb_date'] or '',
            row['comment'] or '',
            row['created_at'],
            row['updated_at'],
        ])

    filename = f"{user['username']}_wainwrights.csv"
    response = app.response_class(
        buffer.getvalue(),
        mimetype='text/csv; charset=utf-8',
    )
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/wainwrights/api/climbs/import', methods=['POST'])
@app.route('/api/climbs/import', methods=['POST'])
def import_climbs():
    user = current_user()
    if user is None:
        return prepare_response({"error": "login required"}, 401)

    upload = request.files.get('file')
    raw_text = ''
    if upload is not None:
        raw_text = upload.stream.read().decode('utf-8-sig')
    else:
        raw_text = request.get_data(as_text=True) or ''

    if not raw_text.strip():
        return prepare_response({"error": "CSV file is empty"}, 400)

    existing_rows = {}
    with sqlite3.connect(USER_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            '''
            SELECT wainwright_id, climbed, climb_date, comment
            FROM user_climbs
            WHERE user_id = ?;
            ''',
            (user['id'],),
        ).fetchall()
        for row in rows:
            existing_rows[row['wainwright_id']] = dict(row)

    imported = []
    warnings = []
    errors = []
    created_count = 0
    updated_count = 0
    unchanged_count = 0

    reader = csv.DictReader(io.StringIO(raw_text))
    required_headers = [
        'wainwright_id',
        'wainwright_name',
        'climbed',
        'climb_date',
        'comment',
        'created_at',
        'updated_at',
    ]
    if reader.fieldnames is None:
        return prepare_response({"error": "CSV header row is missing"}, 400)

    normalized_headers = [header.strip() for header in reader.fieldnames]
    if normalized_headers != required_headers:
        return prepare_response(
            {
                "error": "CSV headers must match: " + ', '.join(required_headers)
            },
            400,
        )

    base_names = {
        row['id']: row['name']
        for row in get_base_wainwright_rows()
    }

    now = iso_now()
    with sqlite3.connect(USER_DB_PATH) as con:
        con.execute('PRAGMA foreign_keys = ON;')
        for line_number, row in enumerate(reader, start=2):
            raw_id = (row.get('wainwright_id') or '').strip()
            if not raw_id:
                errors.append(f'Line {line_number}: wainwright_id is required')
                continue

            try:
                wainwright_id = int(raw_id)
            except ValueError:
                errors.append(f'Line {line_number}: wainwright_id must be an integer')
                continue

            if wainwright_id not in base_names:
                errors.append(f'Line {line_number}: unknown wainwright_id {wainwright_id}')
                continue

            climbed_value = parse_import_bool(row.get('climbed'))
            if climbed_value is None:
                errors.append(f'Line {line_number}: climbed must be a boolean-like value')
                continue

            imported_date = normalize_optional_text(row.get('climb_date'))
            if imported_date is not None:
                try:
                    datetime.strptime(imported_date, '%Y-%m-%d')
                except ValueError:
                    errors.append(f'Line {line_number}: climb_date must be YYYY-MM-DD when provided')
                    continue

            imported_comment = normalize_optional_text(row.get('comment'))
            imported_entry = {
                'wainwright_id': wainwright_id,
                'wainwright_name': row.get('wainwright_name') or base_names[wainwright_id],
                'climbed': 1 if climbed_value else 0,
                'climb_date': imported_date,
                'comment': imported_comment,
                'created_at': row.get('created_at') or now,
                'updated_at': row.get('updated_at') or now,
            }

            existing = existing_rows.get(wainwright_id)
            if not climbed_value:
                if existing is not None:
                    warnings.append(
                        f'Line {line_number}: existing climb for {wainwright_id} would be removed; ignored'
                    )
                imported.append(imported_entry)
                continue

            if existing is None:
                con.execute(
                    '''
                    INSERT INTO user_climbs (
                        user_id, wainwright_id, climbed, climb_date, comment, created_at, updated_at
                    )
                    VALUES (?, ?, 1, ?, ?, ?, ?);
                    ''',
                    (
                        user['id'],
                        wainwright_id,
                        imported_date,
                        imported_comment or '',
                        imported_entry['created_at'],
                        imported_entry['updated_at'],
                    ),
                )
                existing_rows[wainwright_id] = {
                    'climbed': 1,
                    'climb_date': imported_date,
                    'comment': imported_comment or '',
                }
                created_count += 1
                imported.append(imported_entry)
                continue

            update_fields = {}
            warning_fields = []

            if existing.get('climbed', 0) != 1:
                update_fields['climbed'] = 1
                warning_fields.append('climbed')

            if imported_date is not None and existing.get('climb_date') != imported_date:
                update_fields['climb_date'] = imported_date
                warning_fields.append('climb_date')

            if imported_comment is not None and existing.get('comment') != imported_comment:
                update_fields['comment'] = imported_comment
                warning_fields.append('comment')

            if update_fields:
                warning_label = ', '.join(warning_fields) if warning_fields else 'values'
                warnings.append(
                    f'Line {line_number}: existing climb for {wainwright_id} updated ({warning_label})'
                )
                update_fields['updated_at'] = imported_entry['updated_at']
                set_clause = ', '.join([f'{key} = ?' for key in update_fields])
                con.execute(
                    f'''
                    UPDATE user_climbs
                    SET {set_clause}
                    WHERE user_id = ? AND wainwright_id = ?;
                    ''',
                    tuple(update_fields.values()) + (user['id'], wainwright_id),
                )
                updated_count += 1
            else:
                unchanged_count += 1

            imported.append(imported_entry)

    logger.info(
        'import username=%s created=%s updated=%s unchanged=%s warnings=%s errors=%s',
        user['username'],
        created_count,
        updated_count,
        unchanged_count,
        len(warnings),
        len(errors),
    )

    status = 200 if not errors else 400
    return prepare_response(
        {
            "ok": not errors,
            "created": created_count,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "warnings": warnings,
            "errors": errors,
            "rows": imported,
        },
        status,
    )


@app.route('/wainwrights/stats/', methods=['GET'])
@app.route('/stats/', methods=['GET'])
def stats():
    now = datetime.now()
    # Get uptime in human readable form
    td = now - server_starttime
    td_sec = td.seconds
    hour_count, rem = divmod(td_sec, 3600)
    minute_count, second_count = divmod(rem, 60)
    timedelta_str = 'Uptime: {} days, {} hours, {} minutes, {} seconds'.format(td.days, hour_count, minute_count, second_count)
    view_context = resolve_view_context()

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        total_wainwrights = cur.execute('SELECT COUNT(*) FROM wainwrights;').fetchone()[0]
        climbed_wainwrights = cur.execute('SELECT COUNT(*) FROM wainwrights WHERE climbed = ?;', (1,)).fetchone()[0]

    if view_context['view_user'] is not None:
        climbed_wainwrights = get_user_climb_count(view_context['view_user']['id'])

    data = {
        "server_currenttime": now,
        "server_starttime": server_starttime,
        "server_uptime": timedelta_str,
        "server_version": ver,
        "total_wainwrights": total_wainwrights,
        "climbed_wainwrights": climbed_wainwrights,
        "authenticated": view_context['session_user'] is not None,
        "requested_username": view_context['requested_username'],
        "viewed_username": view_context['view_user']['username'] if view_context['view_user'] is not None else None,
        "view_exists": view_context['view_exists'],
        "can_edit": view_context['can_edit'],
        }
    return prepare_response(data, 200)


@app.route('/wainwrights/climbed/', methods=['GET'])
@app.route('/climbed/', methods=['GET'])
def climbed():
    data = [row for row in build_wainwright_payload() if row['climbed'] == 1]

    return prepare_response(data, 200)


@app.route('/wainwrights/api/wainwrights/', methods=['GET'])
@app.route('/api/wainwrights/', methods=['GET'])
@app.route('/wainwrights/', methods=['GET'])
def index():
    lat1 = request.args.get('lat1', type=float)
    lng1 = request.args.get('lng1', type=float)
    lat2 = request.args.get('lat2', type=float)
    lng2 = request.args.get('lng2', type=float)

    if None in (lat1, lng1, lat2, lng2):
        logger.warning(
            'wainwrights request missing_or_invalid_bounds remote_addr=%s',
            request.remote_addr,
        )
        return prepare_response(
            {"error": "lat1, lng1, lat2, and lng2 must be provided as numbers"},
            400,
        )

    lat_min, lat_max = sorted((lat1, lat2))
    lng_min, lng_max = sorted((lng1, lng2))
    view_context = resolve_view_context()

    data = [
        row for row in build_wainwright_payload(view_context)
        if lat_min <= row['lat'] <= lat_max and lng_min <= row['lng'] <= lng_max
    ]

    return prepare_response(data, 200)


@app.route('/wainwrights/api/wainwrights/<int:wainwright_id>', methods=['POST'])
@app.route('/api/wainwrights/<int:wainwright_id>', methods=['POST'])
def update_wainwright(wainwright_id):
    user = current_user()
    if user is None:
        return prepare_response({"error": "login required"}, 401)

    payload = request.get_json(silent=True) or {}
    climbed = bool(payload.get('climbed'))
    climb_date = payload.get('climb_date')
    comment = (payload.get('comment') or '').strip()

    if len(comment) > 100:
        return prepare_response({"error": "comment must be 100 characters or fewer"}, 400)

    if climb_date:
        try:
            datetime.strptime(climb_date, '%Y-%m-%d')
        except ValueError:
            return prepare_response({"error": "climb_date must be YYYY-MM-DD"}, 400)

    now = iso_now()
    with sqlite3.connect(USER_DB_PATH) as con:
        con.execute('PRAGMA foreign_keys = ON;')
        if climbed:
            con.execute(
                '''
                INSERT INTO user_climbs (
                    user_id, wainwright_id, climbed, climb_date, comment, created_at, updated_at
                )
                VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(user_id, wainwright_id) DO UPDATE SET
                    climbed = excluded.climbed,
                    climb_date = excluded.climb_date,
                    comment = excluded.comment,
                    updated_at = excluded.updated_at;
                ''',
                (user['id'], wainwright_id, climb_date, comment, now, now),
            )
        else:
            con.execute(
                'DELETE FROM user_climbs WHERE user_id = ? AND wainwright_id = ?;',
                (user['id'], wainwright_id),
            )

    logger.info(
        'update user=%s wainwright_id=%s climbed=%s climb_date=%s',
        user['username'],
        wainwright_id,
        climbed,
        climb_date,
    )

    return prepare_response({"ok": True}, 200)


if __name__ == '__main__':
    logger.info(
        'startup version=%s host=%s port=%s debug=%s db=%s static_dir=%s',
        ver,
        '0.0.0.0',
        port,
        debug,
        DB_PATH,
        STATIC_DIR,
    )
    app.run(debug=debug, host='0.0.0.0', port=port)

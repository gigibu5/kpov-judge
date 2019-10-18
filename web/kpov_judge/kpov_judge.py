#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import collections
import datetime
import json
import random
import settings
import traceback
import uuid

from kpov_draw_setup import draw_setup
import kpov_util

import pymongo
import flask
from flask import Flask, g, session, redirect, url_for, abort, render_template, flash, app, request, Response
from flask.ext.babel import Babel, gettext, ngettext, format_datetime, _
import jinja2

app = Flask(__name__)
app.config.from_object(settings)
babel = Babel(app)

@babel.localeselector
def get_locale():
    # terrible hack, should store as user preference in the DB
    if '/en/' in request.path:
        return 'en'
    if '/si/' in request.path:
        return 'sl'
    return request.accept_languages.best_match(['sl', 'en'])


@app.before_request
def before_request():
    g.db = pymongo.MongoClient(app.config['DB_URI']).get_default_database()


@app.route('/')
@app.route('/courses/')
def index():
    student_id = flask.app.request.environ.get('REMOTE_USER', 'Nobody')
    courses = g.db.courses.find({}, {'course_id': 1, 'name': 1}).sort('course_id')
    return render_template('index.html', student_id=student_id, courses=courses)


@app.route('/courses/<course_id>/')
def course_tasks(course_id):
    student_id = flask.app.request.environ.get('REMOTE_USER', 'Nobody')
    course = g.db.courses.find_one({'course_id': course_id})
    tasks = g.db.tasks.find({'course_id': course_id}, {'task_id': 1}).sort('task_id')
    if tasks is not None:
        task_list = [i['task_id'] for i in tasks]
    else:
        task_list = []
    return render_template('course_tasks.html', student_id=student_id, tasks=task_list, course=course)


@app.route('/tasks/<course_id>/<task_id>/<lang>/setup.<ending>', methods=['GET'])
def setup_svg(course_id, task_id, lang, ending):
    db = g.db
    fmt, mimetype = {
        'svg':('svg', 'image/svg+xml'),
        'png':('png', 'image/png'),
    }[ending]
    networks = list(db.networks.find({'course_id': course_id, 'task_id': task_id}))
    computers = list(db.computers_meta.find({'course_id': course_id, 'task_id': task_id}))
    return Response(draw_setup(computers, networks, format=fmt,
                          icon_path=app.config['STATIC_DIR']),
                    mimetype=mimetype)


@app.route('/tasks/<course_id>/<task_id>/task.py')
def task_source(course_id, task_id):
    db = g.db
    try:
        return db.tasks.find_one({'course_id': course_id, 'task_id': task_id})['source']
    except:
        return ''


@app.route('/tasks/<course_id>/<task_id>/task.html')
def task_html(course_id, task_id):
    return render_template('task.html', task=task_source(course_id, task_id))


def get_params(course_id, task_id, student_id, db):
    try:
        meta = db.task_params_meta.find_one({'course_id': course_id, 'task_id': task_id})['params']
    except Exception:
        return {'mama': 'ZAKVAJ?'}, {'mama': {'public': True}}

    params = db.task_params.find_one({'course_id': course_id, 'task_id': task_id, 'student_id': student_id})
    if params is None or 'params' not in params: # TODO try with $exists: params or smth.
        try:
            gen_params_source = db.gen_params.find_one({'course_id': course_id, 'task_id': task_id})['source']
            gen_params_code = compile(gen_params_source, 'generator.py', 'exec')
            d = {}
            exec(gen_params_code, globals(), d)
            params = d['gen_params'](student_id, meta)
            db.task_params.update({'course_id': course_id, 'task_id': task_id, 'student_id': student_id},
                {'$set': {'params': params}}, upsert=True)
            params = d['gen_params'](student_id, meta) # TODO this is repeated, is it necessary?
            for computer in db.computers_meta.find({'course_id': course_id, 'task_id': task_id}):
                try:
                    name = computer.pop('name')
                    del computer['_id']
                    del computer['task_id']
                except Exception:
                    pass
                db.student_computers.update({'course_id': course_id, 'task_id': task_id, 'student_id': student_id, 'name': name},
                    {'$set': computer}, upsert=True)
        except Exception as e:
            meta = {'crash': {'public': True}}
            params = {'crash': "Parameter creator crashed or missing:\n{}".format(
                traceback.format_exc())}
    else:
        params = params['params']
    return params, meta


@app.route('/tasks/<course_id>/<task_id>/')
def task_lang_redirect(course_id, task_id):
    return redirect(url_for('task_greeting', course_id=course_id, task_id=task_id, lang=app.config['DEFAULT_LANG']))


@app.route('/tasks/<course_id>/<task_id>/<lang>/howto/')
def task_howto(course_id, task_id, lang):
    db = g.db
    return db.howtos.find_one({'course_id': course_id, 'task_id': task_id, 'lang': lang}).get('text', '')


@app.route('/tasks/<course_id>/<task_id>/<lang>/images/<fname>')
def task_image(course_id, task_id, lang, fname):
    db = g.db
    return db.howto_images.find_one({'course_id': course_id, 'task_id': task_id, 'fname': fname}).get('data', '')


@app.route('/tasks/<course_id>/<task_id>/<lang>/')
def task_greeting(course_id, task_id, lang):
    student_id = flask.app.request.environ.get('REMOTE_USER', 'Nobody')
    db = g.db
    # generate the parameters as soon as the student visits
    params, meta = get_params(course_id, task_id, student_id, db)
    instr_ok = True
    try:
        instructions = db.task_instructions.find_one({'course_id': course_id, 'task_id': task_id})
        instructions = instructions.get(lang, instructions[app.config['DEFAULT_LANG']])
    except Exception:
        try:
            instructions = list(instructions.values())[0]
        except Exception as e:
            instructions = str(e)
            instr_ok = False
    if instr_ok:
        try:
            public_params = []
            for k, v in meta.items():
                if v.get('public', False):
                    public_params += [{
                        'name': k,
                        'value': params.get(k),
                        'description': v.get('descriptions', {}).get(lang)
                    }]
        except Exception as e:
            instructions = str(e)

    computer_list = list(db.student_computers.find({'course_id': course_id, 'task_id': task_id, 'student_id': student_id}))

    backing_files = collections.defaultdict(set)
    for computer in computer_list:
        if 'disk_urls' not in computer:
            continue
        for name, disk in computer['disk_urls'].items():
            for fmt in disk['formats']:
                backing_files[fmt] |= set(disk[fmt][1:])

    if request.args.get('narediStack', 'false') == 'true':
      #db.student_tasks.update({'task_id': task_id, 'student_id': student_id}, {'$set': {'create_openstack': True}}, upsert = True)
        openstackCreated = False # Spremeni na True, ko odkomentiras zgornjo vrstico.
    else:
        if db.student_tasks.find({'course_id': course_id, 'task_id': task_id, 'student_id': student_id, 'openstack_created': True}).count() > 0:
            openstackCreated = True
        elif db.student_tasks.find({'course_id': course_id, 'task_id': task_id, 'student_id': student_id, 'create_openstack': True}).count() > 0:
            openstackCreated = True
        else:
            openstackCreated = False

    try:
        result = db.results.find_one(
            {'$query': {'course_id': course_id, 'task_id': task_id, 'student_id': student_id},
                '$orderby': collections.OrderedDict([('result', -1), ('time', 1)])},
            {'result': 1, 'status': 1, 'hints': 1, 'time': True, '_id': 0})
        result['time'] = format_datetime(result['time'])
        print(result)
    except Exception:
        result = None

    return render_template('task_greeting.html',
        disk_base_url='/'.join([app.config['STUDENT_DISK_URL'], student_id, course_id, task_id, '']),
        course_id=course_id,
        task_id=task_id,
        computers=sorted((c for c in computer_list if 'disk_urls' in c), key=lambda c: c['name']),
        backing_files={fmt: sorted(images) for fmt, images in backing_files.items()},
        lang='sl' if lang == 'si' else lang, # TODO s/si/sl in all tasks (and maybe elsewhere)
        openstack=openstackCreated,
        instructions=jinja2.Template(instructions),
        params=public_params,
        result=result,
        **{p['name']: p['value'] for p in public_params})


@app.route('/tasks/<course_id>/<task_id>/token.json')
def get_token(course_id, task_id):
    db = g.db
    student_id = flask.app.request.environ.get('REMOTE_USER', 'Nobody')
    token = str(uuid.uuid4())
    db.task_params.update({'course_id': course_id, 'task_id': task_id, 'student_id': student_id},
                {'$set': {'token': token}}, upsert=True)
    return json.dumps({'token': token})


@app.route('/tasks/<course_id>/<task_id>/params.json', methods=['POST'])
def params_json(course_id, task_id):
    db = g.db
    token = flask.app.request.form['token']
    record = db.task_params.find_one({'course_id': course_id, 'task_id': task_id, 'token': token})
    if not record:
        return json.dumps({})
    params, meta = get_params(record['course_id'], record['task_id'], record['student_id'], db)
    shown_params = {}
    for name, param in params.items():
        if meta.get(name, {'public': False})['public']:
            shown_params[name] = param
    return json.dumps(shown_params)


@app.route('/tasks/<course_id>/<task_id>/results.json', methods=['POST'])
def results_json(course_id, task_id):
    db = g.db
    token = flask.app.request.form.get('token', '')
    task = db.task_params.find_one({'course_id': course_id, 'task_id': task_id, 'token': token})
    if not task:
        return json.dumps({'result': 0, 'hints': ['invalid token'], 'status': 'NOT OK'})

    params = task['params']
    if params is None:
        return json.dumps({'result': 0, 'hints': ['no parameters found for task'], 'status': 'NOT OK'}) # no such task

    results = json.loads(flask.app.request.form['results'])
    user_params = json.loads(flask.app.request.form['params'])

    meta = db.task_params_meta.find_one({'task_id': task_id})
    if meta is None:
        meta = {}
    else:
        meta = meta['params']
    for param_name, param_meta in meta.items():
        if param_meta.get('w', False) and param_name in user_params:
            params[param_name] = user_params[param_name]

    # hack to get token into task_check function
    # TODO rethink the API
    params['token'] = token
    try:
        task_check_source = db.task_checkers.find_one({'course_id': course_id, 'task_id': task_id})['source']
        d = {}
        exec(compile(task_check_source, 'checker.py', 'exec'), globals(), d)
        res, hints = d['task_check'](collections.defaultdict(str, results), params)
    except Exception as e:
        hints = ["Checker died: " + str(e)]
        res = 0
    if (isinstance(res, int) or isinstance(res, float)) and res > 0:
        res_status = 'OK'
    else:
        res_status = 'NOT OK'

    db.results.insert({
        'course_id': course_id, 'task_id': task_id,
        'result': res, 'hints': hints, 'status': res_status,
        'student_id': task['student_id'],
        'response': results,
        'time': datetime.datetime.now()
    })
    return json.dumps({'result': res, 'hints': hints, 'status': res_status})


if __name__ == '__main__':
    app.run(host='0.0.0.0')

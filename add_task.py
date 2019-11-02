#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import glob
import inspect
import os
import settings
import sys
import urllib

import kpov_util
import pymongo
from bson import Binary

def task_check(results, params):
    data = {
        'results': json.dumps(results),
        'params': json.dumps({k: v for k, v in params.items() if k != 'token'}),
    }
    # should be an argument to task_check, but probably better not modify the signature
    if 'token' in params:
        data['token'] = params['token']

    response = urllib.request.urlopen(
        '{task_url}/{task_name}/results.json'.format(task_url=task_url, task_name=task_name),
        data=urllib.parse.urlencode(data).encode())
    response_dict = json.loads(response.read().decode())
    hints = response_dict.get('hints', [])
    hints = ['status: ' + response_dict.get('status', '')] + hints
    return response_dict.get('result', 'No result'), hints

uploading_task_check_source = inspect.getsource(task_check)

def gen_params(user_id, meta):
    return dict()

dummy_gen_params_source = inspect.getsource(gen_params)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: {0} <task_dir> [task_name]".format(sys.argv[0]))
        exit(1)
    dirname = sys.argv[1]
    fname = os.path.join(dirname, 'task.py')
    try:
        course_id, task_id = sys.argv[2].split('/')
    except:
        normpath = os.path.normpath(dirname)
        course_id = os.path.split(os.path.dirname(normpath))[-1]
        task_id = os.path.basename(normpath)
    print((course_id, task_id))

    db = pymongo.MongoClient(settings.DB_URI).get_default_database()

    source = open(fname).read()
    d = {}
    # defines task, task_check, gen_params, prepare_disks, computers, params_meta
    exec(compile(source, fname, 'exec'), globals(), d)

    public_meta = {}
    for k, v in d['params_meta'].items():
        if v.get('public', False):
            public_meta[k] = v
    task_source = "\n\n".join([
        inspect.getsource(d['task']),
        uploading_task_check_source,
        "params_meta = {}".format(public_meta),
        dummy_gen_params_source])
    task_check_source = inspect.getsource(d['task_check'])
    gen_params_source = inspect.getsource(d['gen_params'])
    prepare_disks_source = inspect.getsource(d['prepare_disks'])
    x = list(d['params_meta'].keys()) # check for existence
    db.computers_meta.remove({'task_id': task_id, 'course_id': course_id})
    auto_networks = set([None])
    for k, v in d['computers'].items():
        for n in v.get('network_interfaces', []):
            auto_networks.add(n.get('network', None))
        db.computers_meta.update({
                'task_id': task_id,
                'course_id': course_id, 
                'name': k
            }, {'$set': v}, upsert=True)
    auto_networks.remove(None)
    db.networks.remove({'task_id': task_id, 'course_id': course_id})
    db.task_params.remove({'task_id': task_id, 'course_id': course_id})
    db.student_computers.remove({'task_id': task_id, 'course_id': course_id})
    db.prepare_disks.remove({'task_id': task_id, 'course_id': course_id})
    try:
        net_list = d['networks'].items()
    except:
        net_list = [(k, {'public': False}) for k in auto_networks]
    for k, v in net_list:
        db.networks.update({'task_id': task_id, 'course_id': course_id, 'name': k}, {'$set': v}, upsert=True)
    db.task_checkers.update({
            'task_id': task_id, 'course_id': course_id
        }, {'$set': {'source': task_check_source}}, upsert=True)
    db.tasks.update({
            'task_id': task_id, 'course_id': course_id
        },{'$set': {'source': task_source}}, upsert=True)
    db.prepare_disks.update({
            'task_id': task_id, 'course_id': course_id
        }, {'$set': {'source': prepare_disks_source}}, upsert=True)
    db.gen_params.update({'task_id': task_id, 'course_id': course_id},
        {'$set': {'source': gen_params_source}}, upsert=True)
    db.task_params_meta.update({'task_id': task_id, 'course_id': course_id},
        {'$set': {'params': d['params_meta']}}, upsert=True)
    db.task_instructions.update({'task_id': task_id, 'course_id': course_id}, 
        {'$set': d['instructions']}, upsert=True)
    for howto_dir in glob.glob(os.path.join(dirname, 'howtos/*')):
        howto_lang = os.path.basename(os.path.normpath(howto_dir))
        if howto_lang not in {'images'}:
            with open(os.path.join(howto_dir, 'index.html')) as f:
                db.howtos.update({
                        'task_id': task_id,
                        'course_id': course_id,
                        'lang': howto_lang},
                    {'$set': {'text': f.read()}}, upsert=True)
        else:
            for img in glob.glob(os.path.join(howto_dir, '*')):
                fname = os.path.basename(img)
                with open(img, 'rb') as f:
                    db.howto_images.update({
                            'task_id': task_id,
                            'course_id': course_id,
                            'fname': fname,
                        },
                        {'$set': {'data': Binary(f.read())}}, upsert=True)

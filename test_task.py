#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import argparse
import collections
import getpass
import inspect
import io
import json
import locale
import os
import random
import readline
import sys
import urllib.request

import yaml
import kpov_util

locale.setlocale(locale.LC_ALL, ['C', 'utf8'])
readline.set_completer_delims(readline.get_completer_delims().replace('/', ''))
readline.parse_and_bind('tab: complete')

TASK_URL = "file://" + os.getcwd() + '/tasks'
PARAMS_FILE = os.path.expanduser("~/.kpov_params.yaml")
DEFAULT_LANGUAGE = 'si'

def print_header(title, spacing=1):
    print('\n'*spacing + '> {}'.format(title))

def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()

# get the parameters for a task either from the user or from a file
def get_params(params, params_meta, language=None):
    # prefill input() prompt with given text
    if language is None:
        language = params.get('language', DEFAULT_LANGUAGE)

    # print all non-writable parameters first, then prompt for writable ones
    for name, meta in sorted(params_meta.items(), key=lambda n: n[1].get('w', True)):
        description = meta.get('descriptions', {}).get(language, name)
        if name not in params:
            params[name] = None
        if meta.get('w', True):
            try:
                if meta.get('masked', False):
                    s = getpass.getpass('{}: '.format(description))
                else:
                    s = rlinput('{}: '.format(description), params.get(name, ''))
                params[name] = s
            except EOFError:
                print()
        else:
            print('{}: {}'.format(name, params.get(name, '')))
    return params

def add_meta_to_argparser(argparser, meta, defaults={}):
    language = defaults.get('language', DEFAULT_LANGUAGE)
    for k, v in meta.items():
        try:
            desc = v['descriptions'][language].encode("utf-8")
        except:
            desc = k
        argparser.add_argument('--'+k, nargs='?', type=str, help=desc,
            default=defaults.get(k, None))

def load_params(filename):
    try:
        return yaml.load(open(filename))
    except:
        return {}

def locate_task(params, argparser, quiet=False):
    # first the URL where all tasks are stored
    url_meta = {
        'task_url': {'descriptions': {'si': 'URL z nalogami', 'en': 'Root URL for all tasks'}}
    }
    if 'task_url' not in params:
        params['task_url'] = TASK_URL
    add_meta_to_argparser(argparser, meta=url_meta, defaults=params)
    args, unknown_args = argparser.parse_known_args()
    params['task_url'] = args.task_url
    if not quiet:
        print_header('Task', spacing=0)
        params = get_params(params, url_meta)

    # and finally, the name of the task
    fetch_params_meta = collections.OrderedDict({'task_name': {'descriptions': {'si': 'Ime naloge', 'en': 'Task name'}}})
    add_meta_to_argparser(argparser, meta=fetch_params_meta, defaults=params)
    args, unknown_args = argparser.parse_known_args()
    # update params with the now known args
    for k, v in fetch_params_meta.items():
        params[k] = vars(args).get(k, params.get(k, None))
    if not quiet:
        params = get_params(params, fetch_params_meta)
    return params

def http_auth(url, username, password):
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, username, password)
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    opener = urllib.request.build_opener(handler)
    urllib.request.install_opener(opener) # now all calls to urlopen use our opener

def load_task(stream):
    # the stream should definitions for the functions task(…),
    # task_check and gen_params, and a dictionary params_meta
    d = {}
    exec(compile(source, 'task.py', 'exec'), globals(), d)
    return d['task'], d['task_check'], d['params_meta'], d['gen_params']


if __name__ == '__main__':
    # get the parameters needed to get to the task, such as the URLs, the name of the task and optionally an ID from the student
    # start with the the parameters needed for the dialog gui to work
    argparser = argparse.ArgumentParser(conflict_handler='resolve',
        description='Test a KPOV Judge task.')
    argparser.add_argument('-h', '--help', action='store_true')
    argparser.add_argument('-q', '--quiet', action='store_true',
        help='disable prompts')
    argparser.add_argument('-g', '--generate_params', action='store_true',
        help='generate initial values for the task parameters')
    argparser.add_argument('-pf', '--params_file', nargs='?', default=PARAMS_FILE,
        help='a local file with saved param values')
    basic_args, unknown_args = argparser.parse_known_args()

    # get default parameters including language
    params = load_params(basic_args.params_file)
    argparser.add_argument('-l', '--language', nargs='?',
        default=params.get('language', DEFAULT_LANGUAGE),
        help='the language used')
    basic_args, unknown_args = argparser.parse_known_args()
    params['language'] = basic_args.language

    if basic_args.help:
        argparser.print_help()
        exit(0)

    # continue with the parameters needed to get the task
    params = locate_task(params, argparser, quiet=basic_args.quiet)
    # TODO: if the task name is missing or invalid, try to get a list of tasks 
    # get task source and generate params if neccessarry
    try:
        task_url = params['task_url']
        task_name = params['task_name']

        source = urllib.request.urlopen("{task_url}/{task_name}/task.py".format(**params)).read()
        if not source:
            raise Exception('no such task: {}'.format(task_name))
        task, task_check, task_params_meta, gen_params = load_task(source)
    except Exception as e:
        print(e)
        with open(basic_args.params_file, 'w') as f:
            yaml.dump(params, f)
        exit(1)

    # get stored task parameters
    params['task_params'] = params.get('task_params', {})
    task_params = params['task_params'].setdefault(task_name, {})
    tokens = params.setdefault('tokens', {})

    # ensure we have a submission token
    if task_url.startswith('http'):
        n_tries = 3
        while n_tries > 0:
            try:
                if tokens.get(task_name):
                    response = urllib.request.urlopen(
                            '{task_url}/{task_name}/params.json'.format(**params),
                            data=urllib.parse.urlencode({'token': tokens.get(task_name)}).encode())
                    response = json.load(io.TextIOWrapper(response))
                    if response:
                        # got params
                        task_params.update(response)
                        break
                    else:
                        # did not get a token, try again with password
                        del tokens[task_name]
                        n_tries -= 1

                if not tokens.get(task_name):
                    # get the student's ID and password
                    # TODO clunky, should refactor all argument-getting stuff
                    user_meta = collections.OrderedDict((
                        ('username', {'descriptions': {'si': 'Uporabniško ime', 'en': 'Username'}}),
                        ('password', {'descriptions': {'si': 'Geslo', 'en': 'Password'}, 'masked': True}),
                    ))
                    print_header('KPOV login')
                    user_params = get_params(params, user_meta, params['language'])

                    http_auth(task_url, user_params['username'], user_params['password'])
                    response = urllib.request.urlopen('{task_url}/{task_name}/token.json'.format(**params))
                    response = json.load(io.TextIOWrapper(response))
                    if response:
                        tokens[task_name] = response['token']
                        params['username'] = user_params['username']
            except Exception as ex:
                print(ex)
    else:
        # use system username to generate parameters
        params['username'] = getpass.getuser()

    if basic_args.generate_params:
	#prejema lahko samo stringe in ne številk (potrebno je str(int)
        # print ("params before: {} {}".format(params, task_params))
        task_params.update(gen_params(params['username'], task_params_meta))
        # print ("params after: {} {}".format(params, task_params))

    task_argparser = argparse.ArgumentParser(parents=[argparser], conflict_handler='resolve', add_help=True)
    add_meta_to_argparser(task_argparser, task_params_meta, defaults=task_params)
    args = vars(task_argparser.parse_args())
    for k in task_params_meta:
        if args.get(k):
            task_params[k] = args[k]
    if not basic_args.quiet:
        print_header('Task parameters')
        task_params = get_params(task_params, task_params_meta, language=params['language'])

    public_params = {}
    for k in inspect.getargs(task.__code__)[0]:
        public_params[k] = task_params[k]
    params['task_params'][params['task_name']] = task_params

    # save parameters for the next run
    with open(basic_args.params_file, 'w') as f:
        yaml.dump(params, f)

    try:
        print_header('Results', spacing=0 if basic_args.quiet else 1)
        print('Running task... ', end='', flush=True)
        task_result = task(**public_params)
        print('checking task... ', end='', flush=True)
        task_params['token'] = tokens.get(task_name, '') # hack to avoid changing task_check signature
        score, hints = task_check(task_result, task_params)
        print('done!')
        print('Score: {}'.format(score))

        print_header('Hints')
        for hint in hints:
            print(hint.strip())
    except Exception as e:
        import traceback
        traceback.print_exc()

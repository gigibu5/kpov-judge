#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import glob
import os
import sys

def print_instructions(p, fname):
    try:
        print("---------------")
        l = p.split(os.sep)
        l1 = []
        for i in range(len(l)):
            f = os.path.join(*l[:i+1])
            if os.path.islink(f):
                s = "{0} ({1})".format(l[i], os.path.split(os.readlink(f))[1])
            else:
                s = l[i]
            l1.append(s)
        print(p)
        print(" - ".join(l1))
        with open(os.path.join(p, fname)) as f:
            task_code = compile(f.read(), fname, 'exec')
            d = {}
            exec(task_code, globals(), d)
            for lang, text in d['instructions'].items():
                print("Language: {0}".format(lang))
                print(text.encode('utf-8'))
                print("")
    except Exception as e:
        print(e)

if __name__ == '__main__':
    l = glob.glob(sys.argv[1])
    l.sort()
    for d in l:
        for root, dirs, files in os.walk(d, followlinks=True):
            for fname in files:
                if fname == 'task.py':
                    print_instructions(root, fname) 

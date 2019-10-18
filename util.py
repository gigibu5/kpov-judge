# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import yaml

def write_default_config(disk, global_params, user='test', uid=1001, gid=None):
    if gid is None:
        gid = uid
    home = '/home/{}'.format(user)
    params_file = os.path.join(home, '.kpov_params.yaml')
    default_params = {}
    for k in [
            'task_name',
            'username',
            'task_url']:
        if k in global_params:
            default_params[k] = global_params[k]
    disk.write(params_file, yaml.dump(default_params))
    disk.chown(uid, gid, params_file)

    mydir = os.path.dirname(os.path.abspath(__file__))
    # write testing script and helper
    for f in ['test_task.py', 'kpov_util.py']:
        src = os.path.join(mydir, f)
        dst = os.path.join(home, f)
        disk.write(dst, open(src).read())
        disk.chmod(0o755, dst)
    disk.copy_in(os.path.join(mydir, 'random_data'), home)

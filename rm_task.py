#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import settings
import sys

import pymongo

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: {0} [task_name]".format(sys.argv[0]))
        exit(1)
    task_id = sys.argv[1]
    db = pymongo.MongoClient(settings.DB_URI).get_default_database()
    db.computers_meta.remove({'task_id': task_id})
    db.networks.remove({'task_id': task_id})
    db.task_checkers.remove({'task_id': task_id})
    db.tasks.remove({'task_id': task_id})
    db.prepare_disks.remove({'task_id': task_id})
    db.student_computers.remove({'task_id': task_id})
    db.results.remove({'task_id': task_id})
    db.gen_params.remove({'task_id': task_id})
    db.task_params_meta.remove({'task_id': task_id})
    db.task_params.remove({'task_id': task_id})
    db.task_instructions.remove({'task_id': task_id})
    db.howtos.remove({'task_id': task_id})
    db.howto_images.remove({'task_id': task_id})

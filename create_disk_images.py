#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import hashlib
import collections
import fcntl
import glob
import inspect
import os
import re
import subprocess
import sys

import guestfs
import pymongo

import settings
import kpov_util
from util import write_default_config

def get_prepare_disks(db, course_id, task_id):
    prepare_disks_source = db.prepare_disks.find_one({'course_id': course_id, 'task_id': task_id})['source']
    d = {}
    exec(compile(prepare_disks_source, 'prepare_disks.py', 'exec'), globals(), d)
    return d['prepare_disks']

def create_snapshot(course_id, task_id, student_id, computer_name, disk_name, fmt='vmdk', overwrite=True):
    # add a hash to filename to allow multiple students using the same directory
    snap_hash = hashlib.sha1((student_id+course_id).encode()).hexdigest()[:3]
    snap = '{}-{}-{}-{}.{}'.format(
        task_id, snap_hash, computer_name, disk_name, fmt)
    backing = []

    template = disk_name + '.' + fmt
    task_dir = os.path.join(student_id, course_id, task_id)
    task_path = os.path.join(settings.STUDENT_DISK_PATH, task_dir)

    if not os.path.exists(os.path.join(task_path)) or overwrite:
        if not os.path.exists(os.path.join(settings.DISK_TEMPLATE_PATH, template)):
            raise Exception('template not found: {}'.format(template))

        # ensure task dir exists
        os.makedirs(task_path, exist_ok=True)

        if fmt in ('vdi', 'vmdk'):
            # don’t use backing files, just copy the template
            os.chdir(task_path)
            if settings.STUDENT_DISK_COW:
                subprocess.call(['cp', '--reflink=always', os.path.join(settings.DISK_TEMPLATE_PATH, template), snap])
            else:
                subprocess.call(['cp', os.path.join(settings.DISK_TEMPLATE_PATH, template), snap])

        elif fmt == 'qcow2':
            # qemu-img create stores backing-file path as given, so link all
            # backing images to task directory where target image will be
            # generated
            os.chdir(settings.DISK_TEMPLATE_PATH) # qemu-img info is saner when called from image directory
            output = subprocess.check_output(
                ['qemu-img', 'info', '--backing-chain', template], universal_newlines=True)
            for image in [template] + [m.group(1) for m in re.finditer(r'backing file: (.*)', output)]:
                backing += [image]
                dest = os.path.join(task_path, image)
                if not os.path.exists(dest):
                    os.symlink(os.path.join(settings.DISK_TEMPLATE_PATH, image), dest)
            # would be great if someone finds a way to avoid the stuff above

            # make overlay image
            os.chdir(task_path)
            subprocess.call(['qemu-img', 'create',
                '-f', fmt,
                '-b', template, snap])

    return task_dir, snap, backing

def prepare_task_disks(course_id, task_id, student_id, fmt, computers):
    disks = collections.defaultdict(dict)
    templates = collections.defaultdict(dict)
    for computer in computers:
        lock_fp.write('creating computer ' + computer['name'] + '\n')
        if not computer['disks']:
            continue

        manual_disks = []
        try_automount = False

        g = guestfs.GuestFS()
        for disk in computer['disks']:
            lock_fp.write("register " + disk['name'] + '\n')
            task_dir, snap, backing = create_snapshot(course_id, task_id, student_id, computer['name'], disk['name'], fmt=fmt)
            snap_file = os.path.join(settings.STUDENT_DISK_PATH, task_dir, snap)
            if 'options' in disk:
                g.add_drive_opts(snap_file, **(disk['options']))
            else:
                g.add_drive(snap_file)
            if 'parts' in disk:
                for p in disk['parts']:
                    lock_fp.write("part {}: {}\n".format(
                        settings.GUESTFS_DEV_PREFIX + p['dev'], p['path']))
                    manual_disks.append(
                        (settings.GUESTFS_DEV_PREFIX + p['dev'], p['path'], p.get('options', None)))
            else:
                try_automount = True

            templates[disk['name']] = g
            lock_fp.write("  templates[{}] = {}\n".format(disk['name'], disk))

            # add disk or update existing record with new format
            disks[computer['name']][disk['name']] = [snap] + backing

        g.launch()
        mounted = set()
        if try_automount:
            roots = g.inspect_os()
            for root in roots:
                mps = g.inspect_get_mountpoints(root)
                lock_fp.write('detected: ' + str(mps) + '\n')
                for mountpoint, device in sorted(mps):
                    if mountpoint not in mounted:
                        try:
                            g.mount(device, mountpoint, )
                            lock_fp.write( 'mounted ' + device + ' on ' + mountpoint + '\n')
                        except RuntimeError as msg:
                            lock_fp.write( "%s (ignored)\n" % msg)
                        mounted.add(mountpoint)

        for device, mountpoint, opts in manual_disks:
            try:
                if opts is not None:
                    g.mount_options(opts, device, mountpoint)
                else:
                    g.mount(device, mountpoint)
                lock_fp.write('manually mounted ' + device + " on " + mountpoint + '\n')
            except RuntimeError as msg:
                lock_fp.write( "%s (ignored)\n" % msg)

    lock_fp.write("preparing disks\n")
    global_params = {
        'task_name': task_id,
        'course_id': course_id,
        'username': student_id
    }
    if 'TASK_URL' in vars(settings):
        global_params['task_url'] = settings.TASK_URL + '/' + course_id + '/'

    task_params = db.task_params.find_one({'course_id': course_id, 'task_id': task_id, 'student_id': student_id})['params']
    prepare_disks = get_prepare_disks(db, course_id, task_id)
    prepare_disks(templates, task_params, global_params)

    # pospravi za seboj.
    lock_fp.write("unmounting\n")
    for g in set(templates.values()):
        g.umount_all()
        g.close()

    return disks

if __name__ == '__main__':
    if len(sys.argv) != 1:
        print("Usage: {0}")
        print("Create the pending disk images")

    db = pymongo.MongoClient(settings.DB_URI).get_default_database()

    all_computers = collections.defaultdict(list)
    for computer in db.student_computers.find({"disk_urls": {"$exists": False}}):
        all_computers[(computer['course_id'], computer['task_id'], computer['student_id'])] += [computer]

    for (course_id, task_id, student_id), computers in all_computers.items():
        if db.student_computers.find_one({'course_id': course_id, 'task_id': task_id, 'student_id': student_id}) is None:
            continue

        lock_file = os.path.join(settings.STUDENT_LOCKFILE_PATH, 
            '{0}-{1}-{2}.lock'.format(student_id, course_id, task_id))
        with open(lock_file, 'w') as lock_fp:
            try:
                fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue

            all_disks = collections.defaultdict(dict)
            for fmt in settings.STUDENT_DISK_FORMATS:
                print("Creating {}/{} for {} [format={}]".format(course_id, task_id, student_id, fmt))
                try:
                    for computer, disks in prepare_task_disks(course_id, task_id, student_id, fmt, computers).items():
                        for disk, urls in disks.items():
                            d = all_disks[computer].setdefault(disk, {'formats': []})
                            d['formats'] += [fmt]
                            d[fmt] = urls
                except Exception as ex:
                    print(ex)
                    continue

            lock_fp.write("saving URLs\n")
            for computer in computers:
                comp_name = computer['name']
                disks = all_disks[comp_name]
                lock_fp.write('urls: '+ str(disks) + '\n')
                db.student_computers.update({
                        'disk_urls': {'$exists': False},
                        'student_id': student_id,
                        'task_id': task_id,
                        'course_id': course_id,
                        'name': comp_name},
                    {'$set': { 'disk_urls': disks }})

            os.unlink(lock_file)

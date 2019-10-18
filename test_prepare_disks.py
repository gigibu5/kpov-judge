#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import fcntl
import glob
import inspect
import os
import sys
import urllib.request

import guestfs
import paramiko
import yaml

import kpov_util
from test_task import http_auth
from util import write_default_config

class SSHGuestFs:
    def __init__(self, hostname, username, password):
        return_results = {}
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, username=username, password=password)
        self.conn = client
    def __del__(self):
        try:
            self.conn.close()
        except:
            pass
    def chmod(self, mode, path):
        self.conn.exec_command('chmod {} "{}"'.format(oct(mode), path))
    def chown(self, owner, group, path):
        self.conn.exec_command('chown {}.{} "{}"'.format(str(owner), str(group), path))
    def command(self, arguments):
        self.conn.exec_command(arguments)
    def cp(self, src, dest):
        self.conn.exec_command('cp "{}" "{}"'.format(src, dest))
    def cp_a(self, src, dest):
        self.conn.exec_command('cp -a "{}" "{}"'.format(src, dest))
    def cp_r(self, src, dest):
        self.conn.exec_command('cp -r "{}" "{}"'.format(src, dest))
    def dd(self, src, dest):
        self.conn.exec_command('dd if="{}" of="{}"'.format(src, dest))
    def df(self):
        stdin, stdout, stderr = self.conn.exec_command('df')
        return stdin.read()
    def download(self, remotefilename, filename):
        stdin, stdout, stderr = self.conn.exec_command('dd if="{}"'.format(path))
        with open(filename, 'w') as f:
            data = stdin.read(4096)
            while data:
                f.write(data)
                data = stdin.read(4096)
    def download_offset (self, remotefilename, filename, offset, size):
        stdin, stdout, stderr = self.conn.exec_command('dd bs=1 skip={} count={} if="{}"'.format(
            offset, size ,path))
        with open(filename, 'w') as f:
            data = stdin.read(4096)
            while data:
                f.write(data)
                data = stdin.read(4096)
    def du(self, path):
        stdin, stdout, stderr = self.conn.exec_command('du "{}"'.format(path))
        return stdin.read()
    def equal(self, file1, file2):
        pass
    def file(self, path):
        stdin, stdout, stderr = self.conn.exec_command('file "{}"'.format(path))
        return stdin.read()
    def ln(self, target, linkname):
        self.conn.exec_command('ln "{}" "{}"'.format(target, linkname))
    def ln_s(self, target, linkname):
        self.conn.exec_command('ln -s "{}" "{}"'.format(target, linkname))
    def ln_f(self, target, linkname):
        self.conn.exec_command('ln -f "{}" "{}"'.format(target, linkname))
    def ln_sf(self, target, linkname):
        self.conn.exec_command('ln -sf "{}" "{}"'.format(target, linkname))
    def getxattrs(self, path):
        pass
        #path = path)
        #stdin, stdout, stderr = self.conn.exec_command('du "{}"'.format(path))
        #return stdin.read()
    def mv (self, src, dest):
        self.conn.exec_command('mv "{}" "{}"'.format(src, dest))
    def mkdir (self, path):
        self.conn.exec_command('mkdir -p "{}"'.format(path))
    def read_file (self, path):
        sftp_client = self.conn.open_sftp()
        f = sftp_client.file(path, mode='r', bufsize=-1)
        s = f.read()
        f.close()
        return s
    def readdir (self, dir):
        sftp_client = self.conn.open_sftp()
        return sftp_client.listdir(path)
    def readlink (self, path):
        stdin, stdout, stderr = self.conn.exec_command('readlink "{}"'.format(path))
        return stdin.read()
    def rename (self, oldpath, newpath):
        return self.mv(oldpath, newpath)
    def rm (self, path):
        stdin, stdout, stderr = self.conn.exec_command('rm "{}"'.format(path))
    def rm_rf (self, path):
        stdin, stdout, stderr = self.conn.exec_command('rm -rf "{}"'.format(path))
    def rmdir (self, path):
        stdin, stdout, stderr = self.conn.exec_command('rmdir "{}"'.format(path))
    def touch (self, path):
        """Touch acts like the touch(1) command. It can be used to
        update the timestamps on a file, or, if the file does
        not exist, to create a new zero-length file.
        
        This command only works on regular files, and will fail
        on other file types such as directories, symbolic links,
        block special etc.
        """
        self.conn.exec_command('touch "{}"'.format(path))
    def setxattr (self, xattr, val, vallen, path):
        pass
    def write (self, path, content):
        """This call creates a file called "path". The content of
        the file is the string "content" (which can contain any
        8 bit data).
        
        See also "g.write_append".
        """
        sftp_client = self.conn.open_sftp()
        f = sftp_client.file(path, mode='w', bufsize=-1)
        f.write(content)
        f.close()

    def write_append (self, path, content):
        """This call appends "content" to the end of file "path".
        If "path" does not exist, then a new file is created.
        
        See also "g.write".
        """
        sftp_client = self.conn.open_sftp()
        f = sftp_client.file(path, mode='a', bufsize=-1)
        f.write(content)
        f.close()

 
if __name__ == '__main__':
    if len(sys.argv) != 1:
        print("Usage: " + sys.argv[0])
        print("Run prepare_disks on running computers over ssh")
        print("The task name and params are read from ~/.kpov_params.yaml")

    yaml_config_file = os.path.expanduser("~/.kpov_params.yaml")
    with open(yaml_config_file) as f:
        params = yaml.load(f)
    task_name = params['task_name']
    try:
        task_url = params['task_url']
        task_name = params['task_name']
        if task_url.startswith('http'):
            http_auth(task_url, params['username'], params['password'])
        req = urllib.request.Request("{task_url}/{task_name}/task.py".format(**params))
        source = urllib.request.urlopen(req).read()
        if not source:
            raise Exception('no such task: {}'.format(task_name))
        d = {}
        exec(compile(source, 'task.py', 'exec'), globals(), d)
        computers, prepare_disks = d['computers'], d['prepare_disks']
    except Exception as e:
        print(e)
        exit(1)

    templates = dict()
    sshguestfs_params = params.get('sshguestfs_params', dict())
    task_sshguestfs_params = sshguestfs_params.get(task_name, dict())
    for computer_name, computer in computers.items():
        comp_params = task_sshguestfs_params.get(computer_name, dict())
        for k in ['hostname', 'username', 'password']:
            try:
                p = comp_params[k]
            except:
                p = input("{} {}:".format(computer_name, k))
            comp_params[k] = p
        comp_connection = None
        try:
            comp_connection = SSHGuestFs(**comp_params)
            task_sshguestfs_params[computer_name] = comp_params
        except Exception as e:
            print(e)
            task_sshguestfs_params.pop(computer_name, None)
        for disk in computer['disks']:
            disk_name = disk['name']
            templates[disk_name] = comp_connection
    sshguestfs_params[task_name] = task_sshguestfs_params
    params['sshguestfs_params'] = sshguestfs_params
    with open(yaml_config_file, 'w') as f:
        # print "dumping", params
        yaml.dump(params, f)
    prepare_disks(templates, params['task_params'][task_name], params)

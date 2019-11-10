#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import collections
import glob
import itertools
import math
import os
import random
import re
import socket
import string
import struct
import subprocess

def ssh_test(host, user, password, commands=()):
    import pexpect
    from pexpect import pxssh

    results = collections.defaultdict(str)
    try:
        s = pxssh.pxssh(encoding='utf-8', timeout=10)
        s.login(host, user, password,
            original_prompt='~[#$] ',
            auto_prompt_reset=False)
        results['ssh'] = True
        results['motd'] = s.before
        s.set_unique_prompt()
        for test, command in commands:
            s.sendline(command)
            s.prompt()
            if test:
                results[test] = s.before[len(command+'\r\n'):].strip().replace('\r\n', '\n')
        s.logout()
    except pexpect.exceptions.EOF as e:
        results['ssh'] = 'connection to {} as {}/{} failed (EOF)'.format(host, user, password)
    except pexpect.exceptions.TIMEOUT as e:
        results['ssh'] = 'connection to {} as {}/{} failed (timeout)'.format(host, user, password)
    except Exception as e:
        results['ssh'] = 'connection to {} as {}/{} failed ({})'.format(host, user, password, e)
    return results

# omit i, l, o, I, O, 1, 0 for readability
uppers = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
lowers = 'abcdefghjkmnpqrstuvwxyz'
digits = '23456789'
def alnum_gen(r, length=1, digit=True, lower=True, upper=True):
    return ''.join(
        r.choice(
            (digits if digit else '') +
            (lowers if lower else '') +
            (uppers if upper else ''))
        for i in range(length))

def fortune(r, max_len):
    # ask fortune where it stores its cookies
    paths = subprocess.run(['fortune', '-f'], stderr=subprocess.PIPE, universal_newlines=True).stderr.splitlines()
    fortune_dir = paths[0].split()[-1]

    # make a list of all fortunes
    all_fortunes = []
    for fortune_file in glob.iglob(f'{fortune_dir}/*.u8'):
        f = open(fortune_file)
        l = f.read().split('\n%\n')[:-1]
        for i in l:
            if len(i) < max_len:
                all_fortunes.append(i)
    stripped = re.sub(r'\s+', ' ', r.choice(all_fortunes))
    s = re.sub(r'[^\w?:;!./&%$=,]+', ' ', stripped)
    return s.strip()

def _net_to_int(s):
    try:
        net, subnet = s.split('/')
    except ValueError:
        subnet = '32'
    try:
        subnet_int = int(subnet)
    except ValueError:
        subnet_bytes = struct.unpack('>I', socket.inet_aton(subnet))[0]
        max_bit = 1 << 31
        subnet_int = 0
        while (subnet_bytes & max_bit) > 0:
            subnet_int += 1
            max_bit >>= 1
    return struct.unpack('>I', socket.inet_aton(net))[0], subnet_int
            
def IPv4_subnet_gen(r, base_net, mask = 24):
    base_addr, base_subnet = _net_to_int(base_net)
    a = r.randint(1, 1 << mask - base_subnet) << (32 - mask)
    if a >= 1<<32:
        a = 0
    net_addr = base_addr | a
    return socket.inet_ntoa(struct.pack('>I', net_addr)) + '/{0}'.format(mask)

def IPv4_net_gen(r, min_hosts=254, local=True, multicast=False):
    mask = 32 - int(math.ceil(math.log(min_hosts, 2)))
    if local and not multicast:
        net = r.choice([
            "192.168.0.0/16",
            '10.0.0.0/8',
            '172.16.0.0/12'])
    if multicast:
        if local:
            net = "239.255.0.0/16"
        else:
            net = "224.0.0.0/4"
    return IPv4_subnet_gen(r, net, mask)

def IPv4_addr_gen(r, network, n_generated=1, reserve_top=1, reserve_bottom=1):
    net, mask = _net_to_int(network)
    hosts = []
    l = r.sample(list(range(reserve_bottom,
        2**(32 - mask)-reserve_top)), n_generated)
    for i in l:
        hosts.append(socket.inet_ntoa(struct.pack('>I', net | i)))
    return hosts

def MAC_gen(r):
    s = "0123456789ABCDEF"
    return ":".join([r.choice(s) + r.choice("26AE")] + \
        [r.choice(s) + r.choice(s) for i in range(5)])

common_file_extensions = ['jpg', 'png', 'txt', 'doc', 'cfg', 'pdf', 'odt', 'cpp', 'c', 'sh', 'java']
def fname_gen(r, extension=True):
    s = alnum_gen(r, length=5, upper=False)
    if extension:
        s += '.' + r.choice(common_file_extensions)
    return s

fdir = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(fdir, 'random_data/greek_gods.txt')) as f:
    greek_gods = [i.strip() for i in f.readlines()]
with open(os.path.join(fdir, 'random_data/roman_gods.txt')) as f:
    roman_gods = [i.strip() for i in f.readlines()]
with open(os.path.join(fdir, 'random_data/slavic_gods.txt')) as f:
    slavic_gods = [i.strip() for i in f.readlines()]

gods = greek_gods + roman_gods + slavic_gods

def hostname_gen(r):
    return "{0}-{1:02}".format(r.choice(gods), r.randint(1, 99))

with open(os.path.join(fdir, 'random_data/slovenian_names.txt')) as f:
    names = [i.strip() for i in f.readlines()]

with open(os.path.join(fdir, 'random_data/slovenian_surnames.txt')) as f:
    surnames = [i.strip() for i in f.readlines()]

def username_gen(r):
    return ("{}{}{}".format(r.choice(names), r.choice(surnames), r.randint(1, 99))).lower()

def unknown_generator(r):
    return ''

default_generators = {
    'IP': lambda r: IPv4_addr_gen(r, IPv4_net_gen(r))[0],
    'localnet': lambda r: IPv4_net_gen(r, min_hosts = r.randint(16, 250), local=True, multicast=False),
    'filename': fname_gen,
    'dirname': lambda r: fname_gen(r, extension = False),
    'username': username_gen,
    'password': lambda r: alnum_gen(r, 8),
    'short_text': lambda r: fortune(r, 40),
    'uint': lambda r: r.randint(0, 2**32),
    'hostname': lambda r: hostname_gen(r),
    None: lambda r: alnum_gen(r, 8),
    '': unknown_generator,
}


def default_gen(userID, param_meta):
    r = random.Random(userID)
    params = dict()
    for name, meta in param_meta.items():
        if meta.get('generated', False):
            params[name] = default_generators.get(
                meta.get('type', None), unknown_generator)(r)
    return params

if __name__ == '__main__':
    r = random.Random()
    for k, v in default_generators.items():
        print("---{}---".format(k))
        print(v(r))

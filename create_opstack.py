# SPDX-License-Identifier: AGPL-3.0-or-later

import keystoneclient.v2_0.client as ksclient
import quantumclient.quantum.client as qclient
import novaclient.client as nclient
import settings
import pymongo
import sys
import os
import fcntl

##########################################################
      
def create_network(qc, network_name, tenant_name):
    net = {'name': network_name, 'admin_state_up': True, 'tenant_id': getattr(kc.tenants.find(name=tenant_name), 'id')}
    network = qc.create_network({'network': net})
    sub = {'name': network_name + "-subnet", 'cidr': '0.0.0.0/24', 'network_id': network['network']['id'], 'ip_version': 4, 'enable_dhcp': False, 'gateway_ip': None}
    subnet = qc.create_subnet({'subnet': sub})
    return network
  
def get_nova_client(tenant_name):
    return nclient.Client("1.1", username=settings.OS_ADMIN_USER, api_key=settings.OS_ADMIN_PASS, auth_url=settings.OS_AUTH_URL, project_id=tenant_name)

def get_quantum_client(tenant_name):
    kcsub = ksclient.Client(auth_url=settings.OS_AUTH_URL, username=settings.OS_ADMIN_USER, password=settings.OS_ADMIN_PASS, tenant_name=tenant_name)
    client = qclient.Client('2.0', endpoint_url=settings.OS_QUANTUM_URL, token=kcsub.auth_token)
    client.format = 'json'
    return client
     

##########################################################
def main():
    kc = ksclient.Client(endpoint=settings.OS_ADMIN_AUTH_URL, token=settings.OS_ADMIN_TOKEN)
    admin_role = kc.roles.find(name='admin')
    member_role = kc.roles.find(name='Member')

    db = pymongo.MongoClient(settings.DB_URI).get_default_database()
    l = db.student_tasks.find({'create_openstack': True})
    projects = list()
    for project in l:
        task_id, student_id = project['task_id'], project['student_id']
        if (task_id, student_id) not in projects:
            projects.append((task_id, student_id))
    #projects = [ ('01.predvaja','at9036@student.uni-lj.si'), ('01.predvaja', 'andrejtolic@fri1.uni-lj.si') ]
    for task_id, student_id in projects:
        l = db.student_tasks.find_one({'task_id': task_id, 'student_id': student_id, "create_openstack": True})
        if l is None:
            continue
        lock_file = os.path.join(settings.OS_LOCKFILE_PATH, '{0}-{1}.lock'.format(student_id, task_id))
        lock_fp = open(lock_file, 'w')
        try:
            fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            continue
        # Ustvarimo projekt
        project_name = "{0}-{1}".format(student_id, task_id)
        project = kc.tenants.create(tenant_name=project_name)
        lock_fp.write("Created project {0}.\n".format(project_name))
        # Dodamo admin uporabnika v projekt
        kc.roles.add_user_role(kc.users.find(name='admin'), admin_role, project)
        lock_fp.write("Added user admin to project {0}.\n".format(project_name))
        # Ustvarimo L2 omrezja
        qc = get_quantum_client(tenant_name=project_name)
        network_list = db.networks.find({'task_id': task_id})
        nets = {}
        for n in network_list:
            net = create_network(qc, network_name=n['name'], tenant_name=project_name)
            lock_fp.write("Created network {0}.".format(n['name']))
            nets[n['name']] = {'net-id': net['network']['id']}
            db.student_networks.update({'task_id': task_id, 'student_id': student_id, 'name': n['name']}, {'$set': {'network_id': net['network']['id'], 'public': n['public']}}, upsert=True)
        #Ustvarimo instance
        instance_list = db.computers_meta.find({'task_id': task_id})
        nc = get_nova_client(tenant_name=project_name)
        first_instance_in_project = True
        for inst in instance_list:
            image = nc.images.find(name=inst['image'])
            flavor = nc.flavors.find(name=inst['flavor'])
            instance_nets = [nets[iface['network']] for iface in inst['network_interfaces']]
            if inst['config_drive']:
                if 'string' in inst['userdata'].keys():
                    udata = inst['userdata']['string']
                elif 'file' in inst['userdata'].keys():
                    try:
                        udata = open(inst['userdata']['file'], 'r')
                    except:
                        udata = None
                        lock_fp.write("Problem reading file {0} for config drive. Using None instead.".format(inst['userdata']['file']))
            else:
                udata = None
            if first_instance_in_project:
                scheduler_hints = None
                first_instance_in_project = False
            else:
                s = db.student_computers.find_one({'task_id': task_id, 'student_id': student_id, 'name': inst['name']})
                # Value corresponding to the 'same_host' key is a list (with just one element)
                # of instances besides which to put the new instance.
                scheduler_hints = {'same_host': [s['openstack_instance_id']] }
            instance = nc.servers.create(name=project_name + "-" + inst['name'], image=image, flavor=flavor, nics=instance_nets, config_drive=inst['config_drive'], userdata=udata, scheduler_hints=scheduler_hints)
            lock_fp.write("Created instance for computer {0}.".format(inst['name']))
            # Write openstack instance id to mongo.
            db.student_computers.update({'task_id': task_id, 'student_id': student_id, 'name': inst['name']}, {'$set': {'openstack_instance_id': instance['id'], 'openstack_host': instance['OS-EXT-SRV-ATTR:host'], 'openstack_finalized': False}, upsert=True)
            # instance['status'] lahko BUILD, ACTIVE ali SHUTOFF
            # instance = nova.servers.get(instance['id'])
        db.student_tasks.update({'task_id': task_id, 'student_id': student_id}, {'$set': {'create_openstack': False, 'openstack_created': True}})
        os.unlink(lock_file)
        lock_fp.close()
    
    # TODO v loceni skripti.
    # povezi test-net na brarbiters, po izklopu instanc guestfs nad diski in create_image.
    # Dodamo studenta v projekt
    kc.roles.add_user_role(kc.users.find(name=student_id), member_role, project)

if __name__ == '__main__':
    main()

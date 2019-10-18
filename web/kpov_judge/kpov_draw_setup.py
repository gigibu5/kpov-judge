# SPDX-License-Identifier: AGPL-3.0-or-later

import pygraphviz as pgv

def draw_setup(computers, networks, destination=None,
               icon_prefix = '../../../static/icons/',
               format='svg', icon_path = '', icon_suffix = None):
    if icon_suffix is None:
        icon_suffix = format
    icon_suffix = '.' + icon_suffix
    G = pgv.AGraph(imagepath=icon_path + '/')
    print(G.graph_attr)
    have_internet = []
    for net in networks:
        net_name = net.get('name', 'net')
        if net.get('public', False):
            have_internet.append(net_name)
        G.add_node('net-' + net_name, label=net_name, shape='rectangle')
    if len(have_internet):
        G.add_node('net-' + 'internet', 
                   label='internet',
                   labelloc='b', 
                   image=icon_prefix + 'internet' + icon_suffix, 
                   shape='none')
        for n in have_internet:
            G.add_edge('net-' + n, 'net-internet')
    for properties in computers:
        c = properties.get('name', '')
        label_str = '< <TABLE BORDER="0"><TR><TD COLSPAN="2"><B>{}</B></TD></TR><TR><TD COLSPAN="2"><IMG SRC="{}"/></TD></TR>'
        label = label_str.format(c, icon_prefix + 'computer' + icon_suffix)
        for hdd in properties.get('disks', []):
            icon = icon_prefix + 'drive-harddisk' + icon_suffix
            label += '<TR><TD><IMG SRC="{}" /></TD><TD>{}</TD></TR>'.format(icon, hdd['name'])
        label += '</TABLE> >'
        G.add_node('comp-' + c,
                   label = label,
                   shape='box', labelloc='b')
        for iface in properties.get('network_interfaces', []):
            G.add_edge('comp-' + c, 'net-' + iface['network'])
    return G.draw(path=destination, format=format, prog='dot')

if __name__ == '__main__':
    import sample_task as task
    print(draw_setup(task.computers, task.networks))
    

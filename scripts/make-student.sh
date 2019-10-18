#!/bin/sh

# Create the disk image for a basic terminal computer with sshd.
# Typical virtual‐machine network interfaces are configured for DHCP.

set -e

if [ $# -lt 1 ]; then
        echo "usage: ${0} base"
        exit 1
fi

base="${1}"
name="student"
format="qcow2"

file_interfaces=\
'# see interfaces(5)
source /etc/network/interfaces.d/*

# loopback interface
auto lo
iface lo inet loopback

# first interface
allow-hotplug ens3
iface ens3 inet dhcp
allow-hotplug enp0s3
iface enp0s3 inet dhcp
'

qemu-img create -f qcow2 -b "${base}" "${name}.${format}"

virt-customize -a "${name}.${format}" \
	--hostname "${name}" \
	--update \
	--install openssh-server \
	--write /etc/network/interfaces:"${file_interfaces}"

#virt-sparsify "${name}.${format}" "${name}x.${format}"
#qemu-img create -f "${format}" -b "${name}x.${format}" "${name}-diff.${format}"
#qemu-img rebase -b "${base}" "${name}-diff.${format}"

#!/bin/sh

# Create the disk image for arbiter: a gateway with NAT, dnsmasq and
# sshd. The user account test / test is set up to run the test_task
# script for evaluating the given task. The account is also given sudo
# rights to reboot, poweroff, ifconfig, ip and mount.

set -e

if [ $# -lt 1 ]; then
        echo "usage: ${0} base"
        exit 1
fi

base="${1}"
name="arbiter"
format="qcow2"

# WAN on first interface, LAN on second
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

# second interface
allow-hotplug ens4
iface ens4 inet static
    address 10.94.94.1/24
allow-hotplug enp0s8
iface enp0s8 inet static
    address 10.94.94.1/24
'

# NAT rules
file_nftables=\
'table ip nat {
        chain prerouting {
                type nat hook prerouting priority 0; policy accept;
        }

        chain postrouting {
                type nat hook postrouting priority 100; policy accept;
                oifname "ens3" masquerade
                oifname "enp0s3" masquerade
        }
}
'

file_dnsmasq=\
'interface=ens4
interface=enp0s8

dhcp-range=10.94.94.16,10.94.94.250,12h
'

file_sudoers=\
'test ALL = /sbin/reboot
test ALL = /sbin/poweroff
test ALL = NOPASSWD: /bin/ip
test ALL = NOPASSWD: /bin/mount
test ALL = NOPASSWD: /sbin/ifconfig
'

qemu-img create -f qcow2 -b "${base}" "${name}.${format}"

virt-customize -a "${name}.${format}" \
	--hostname "${name}" \
	--update \
	--install fortune-mod,fortunes,fortunes-bofh-excuses,python3-pexpect,python3-paramiko,python3-snimpy,python3-yaml \
	--install dnsmasq \
	--install openssh-server \
	--run-command "apt clean" \
	--write /etc/network/interfaces:"${file_interfaces}" \
	--write /etc/nftables.conf:"${file_nftables}" \
	--write /etc/sysctl.d/gateway.conf:"net.ipv4.ip_forward = 1" \
	--run-command "systemctl enable nftables.service" \
	--write /etc/dnsmasq.d/kpov-gw:"${file_dnsmasq}" \
	--run-command "useradd -m -s /bin/bash -p '\$6\$VdV5y2gl\$YxpYuwcVZHSXiv0N4yzmF8PspBeIK8QLdGJZzYFuKRjkfc82DhaS5fQeuOt0q9APDPLeSMTzt8BtxI2Bwo/hH.' test" \
	--write /etc/sudoers.d/kpov-test:"${file_sudoers}"

## make a sparse diff
#virt-sparsify "${name}.${format}" "${name}x.${format}"
#qemu-img create -f "${format}" -b "${name}x.${format}" "${name}-diff.${format}"
#qemu-img rebase -b "${base}" "${name}-diff.${format}"

#rm -f "./${name}-install.${format}"

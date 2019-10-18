#!/bin/sh

# Create the base disk image: a minimal Debian install with a user
# account student / vaje. Root password is kaboom. Serial console is
# enabled for grub and boot messages are displayed. Some useful
# additional packages are installed, and the image is sparsified
# (requires at least 30 GB free space).

set -e

if [ $# -lt 1 ]; then
	echo "usage: ${0} image-name"
	exit 1
fi

name="${1}"
format=qcow2

outfile="${name}.${format}"
fatfile="${name}-fat.${format}"

tmpdir="$(mktemp -d kpov-tmp.XXXXXX)"
trap 'rm -rf "${tmpdir}"' EXIT

for f in linux initrd.gz; do
	wget "https://d-i.debian.org/daily-images/i386/daily/netboot/debian-installer/i386/${f}" -O "${tmpdir}/${f}"
done

qemu-img create -f "${format}" -o size=30G "${fatfile}"

qemu-system-i386 \
	-enable-kvm \
	-nographic \
	-m 1G -smp 2 \
	-kernel "${tmpdir}/linux" -initrd "${tmpdir}/initrd.gz" \
	-append "console=ttyS0,115200n8 serial auto=true url=http://10.0.2.10:8080/preseed.cfg hostname=${name} domain=" \
	-net user,guestfwd=:10.0.2.10:8080-cmd:"/bin/busybox httpd -i" -net nic \
	-hda "${fatfile}"

virt-customize -a "${fatfile}" \
	--update \
	--install virtualbox-guest-utils,virtualbox-guest-modules \
	--install net-tools,nftables \
	--install build-essential,git,nano,vim \
	--install rsync,sudo,tmux \
	--run-command 'apt clean' \
	--edit /etc/default/grub:'s/^GRUB_CMDLINE_LINUX_DEFAULT=.*$/GRUB_CMDLINE_LINUX_DEFAULT="console=tty0 console=ttyS0"/' \
	--edit /etc/default/grub:'s/^GRUB_TERMINAL=.*$/GRUB_TERMINAL=\"console serial\"/' \
	--run-command update-grub

virt-sparsify "${fatfile}" "${outfile}"
rm -f "${fatfile}"

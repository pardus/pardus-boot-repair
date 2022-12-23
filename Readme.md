# Pardus Boot Repair
Boot repair tool for pardus.

## Features:
* grub repair
* password change
* create chroot shell
* reinstallation
* reset user config
* repair partition
* fix broken packages
* full system update

## Installation:
Run this command as root
```shell
make install
```

## Dependencies:
* libc6
* live-boot
* zenity

## Testing:
1. Boot live from media.
1. Fetch source and install.
1. Open terminal and run `pardus-boot-repair` as root

#!/bin/bash
list_partition(){
    for disk in $(ls /sys/block/* | grep "[0-9]$") ; do
        os=$(search-operating-system | grep $disk | cut -f 1 -d ':' | sed "s/ /-/g")
        echo "$disk ($os)"
    done
}

select_user(){
    timeout 3 mount -o defaults,ro /dev/$disk /mnt
    zenity --list \
           --title="Select user" \
           --cancel-label="Exit" \
           --ok-label="Select" \
           --column="User" \
           $(grep -e ":x:[0-9][0-9][0-9][0-9]:" /mnt/etc/passwd | cut -f 1 -d ':') \
           root
    umount /mnt
}

disk=$(zenity --list \
        --title="Select rootfs partition" \
        --cancel-label="Exit" \
        --ok-label="Select" \
        --column="Rootfs partition" \
        --column="" \
        $(list_partition) | cut -f 1 -d ' ')
if [[ "$disk" == "" ]] ; then
    exit 0
fi
while true ; do
    selection=$(zenity --list \
        --title="Pardus Boot Repair" \
        --cancel-label="Exit" \
        --ok-label="Select" \
        --column="Action" --column="Name" \
        "grub"       "Reinstall grub" \
        "password"   "Reset password" \
        "chroot"     "Open chroot shell" \
    )
    if [[ "$selection" == "grub" ]] ; then
        mbr=$(zenity --list \
            --title="Select grub disk" \
            --cancel-label="Exit" \
            --ok-label="Select" \
            --column="Grub disk" \
            $(ls /sys/block/ | grep -v "loop"))
        if [[ "$mbr" == "" ]] ; then
            exit
        fi
        if [[ -d /sys/firmware/efi/ ]] ; then
            efi=$(zenity --list \
                --title="Select efi partition" \
                --cancel-label="Exit" \
                --ok-label="Select" \
                --column="EFI Partition" \
                --column="" \
                $(list_partition))
            if [[ "$efi" == "" ]] ; then
                exit
            fi
        fi
        x-terminal-emulator -e "env disk=$disk mbr=$mbr efi=$efi grub-reinstall"
    elif [[ "$selection" == "password" ]] ; then
        user=$(select_user)
        x-terminal-emulator -e "env user=$user disk=$disk reset-password"
    elif [[ "$selection" == "chroot" ]] ; then
        xhost +
        user=$(select_user)
        x-terminal-emulator -e "pardus-chroot /dev/$disk su $user -"
    else
        exit 0
    fi
done



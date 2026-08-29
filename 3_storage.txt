# Step 1: Find storage devices on pi:
## On pi run:
    lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS,MODEL
##output:
    admin@owl:~$ lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS,MODEL
    NAME          SIZE FSTYPE MOUNTPOINTS    MODEL
    loop0           2G swap
    sda         114.6G                       SanDisk 3.2Gen1
    └─sda1      114.6G exfat
    mmcblk0      29.7G
    ├─mmcblk0p1   512M vfat   /boot/firmware
    └─mmcblk0p2  29.2G ext4   /
    zram0           2G swap   [SWAP]
## Then:
    df -h
##output:
    admin@owl:~$ df -h
    Filesystem      Size  Used Avail Use% Mounted on
    udev            3.6G     0  3.6G   0% /dev
    tmpfs           1.6G  9.1M  1.6G   1% /run
    /dev/mmcblk0p2   29G  5.0G   23G  19% /
    tmpfs           3.9G     0  3.9G   0% /dev/shm
    tmpfs           5.0M   16K  5.0M   1% /run/lock
    tmpfs           1.0M     0  1.0M   0% /run/credentials/systemd-journald.service
    tmpfs           3.9G  4.0K  3.9G   1% /tmp
    /dev/mmcblk0p1  505M   67M  439M  14% /boot/firmware
    tmpfs           1.0M     0  1.0M   0% /run/credentials/serial-getty@ttyS0.service
    tmpfs           1.0M     0  1.0M   0% /run/credentials/getty@tty1.service
    tmpfs           782M   12K  782M   1% /run/user/1000

-------------------------------------------------------------------------------------
## Mount SSD at /srv/pi-security/storage
## Organize like:
    /srv/pi-security/
    ├── storage/                  ← SSD mount
    │   ├── recordings/
    │   │   └── camera01/
    │   ├── events/
    │   └── snapshots/
    ├── config/
    ├── logs/
    └── scripts/
## Multiple cameras:
recordings/
    ├── camera01/
    ├── camera02/
    ├── camera03/
    └── camera04/
-------------------------------------------------------------------------------------

# Step 2: Temporarily mount drive:
    sudo mkdir -p /mnt/pi-security-ssd
    sudo mount /dev/sda1 /mnt/pi-security-ssd
## Then:
    ls -lah /mnt/pi-security-ssd
    du -shk /mnt/pi-security-ssd

# Step 3: ## Change drive from exFat -> ext4
## Stop the recorder
    sudo systemctl stop pi-security-recorder.service 
## Verify: 
    systemctl status pi-security-recorder --no-pager
## Unmount SSD:
    sudo umount /mnt/pi-security-ssd/
## Verify:
    lsblk -0 NAME,SIZE,FSTYPE,MOUNTPOINTS,MODEL
## Format as ext4:
    sudo mkfs.ext4 -L PI_SECURITY /dev/sda1
## Run when finished:
    lsblk -f

# Step 4: Mount the drive:
## Create path:
    sudo mkdir -p /srv/pi-security/storage
## Add ssd to /etc/fstab:
    sudo nano /etc/fstab
## Add to bottom:
    UUID=c2a58269-5ea0-4844-bb98-313fd72e1a6d /srv/pi-security/storage ext4 defaults,nofail 0 2
## Run:
    sudo mount -a
## Reload daemon:
    systemctl daemon-reload
## Verify:
    findmnt /srv/pi-security/storage
    df -h /srv/pi-security/storage

# Step 5: Build storage structure
    /srv/pi-security/
    ├── recordings/        ← existing recordings currently on SD
    └── storage/           ← SSD
        ├── recordings/
        │   └── camera01/
        ├── events/
        └── snapshots/
## Create paths above:
    sudo mkdir -p /srv/pi-security/storage/recordings/camera01
    sudo mkdir -p /srv/pi-security/storage/events
    sudo mkdir -p /srv/pi-security/storage/snapshots
## Give admin ownership:
    sudo chown -R admin:admin /srv/pi-security/storage
## Verify:
    ls -lah /srv/pi-security/storage

# Step 6: Check and copy existing recordings
## Check how much footage is on sd
    du -sh /srv/pi-security/recordings
    ls -lh /srv/pi-security/recordings
## Stop recorder:
    sudo systemctl stop pi-security-recorder
## Verify:
    systemctl is-active pi-security-recorder
## Copy existing recordings to ssd:
    rsync -avh --progress /srv/pi-security/recordings/ /srv/pi-security/storage/recordings/camera01/
## Compare source and destination
    du -sh /srv/pi-security/recordings
    du -sh /srv/pi-security/storage/recordings/camera01
## Compare file counts:
    find /srv/pi-security/recordings -type f | wc -l
    find /srv/pi-security/storage/recordings/camera01 -type f | wc -l
# Step 7: Point recorder at ssd
## Open service file:
    sudo nano /etc/systemd/system/pi-security-recorder.service
## Change: /srv/pi-security/recordings/
## To :/srv/pi-security/storage/recordings/camera01/
## Reload system
    sudo systemctl daemon-reload
## Start recorder:
    sudo systemctl start pi-security-recorder
## Verify its running:
    systemctl status pi-security-recorder --no-pager
## Create test segment
   ls -lh /srv/pi-security/storage/recordings/camera01 | tail 
## Confirm ssd itself is receiving data:
    df -h /srv/pi-security/storage

# Step 7: Remove files from sd
## On the pi:
    rm -f /srv/pi-security/recordings/*.mp4
## Verify old directory is empty:
    ls -lah /srv/pi-security/recordings
## Check sd-card space:
    df -h /


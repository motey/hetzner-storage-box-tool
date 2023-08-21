# hetzner-storage-box-tool
CLI-bash-tool for some common tasks with a hetzner storage box written in python

State: WIP (not usable yet)


# reqs
sshpass
ssh-keygen
ssh-keyscan


# ENV Vars

HSBT_CONNECTIONS_CONFIG_FILE path for the configuration json file.
HSBT_PASSWORD - Password for the hetzner storage box user.
HSBT_SSH_KEY_FILE_DIR - If key is not in ~/.ssh you can provide an alternative dir here


# Basic Usage

**(This is just a documention preview. Package is not yet usable)**

`hsbt --help`

## Create connection

`hsbt setConnection -i myBox1 -u u111111 -h u111111.your-storage.de -o`

```bash
Directory to store ssh private and public key [~/.ssh/]: ↩️
Password for Hetzner Storage Box user myBox1: ...↩️
Saved connection at '/home/tim/.config/hetzner_sbt_connections.json' as:
        identifier='myBox1' host='u111111.your-storage.de' user='u111111' key_dir='~/.ssh/'
```

## use connection

`hsbt remoteCmd -i myBox1 "ls -la"`
```bash
total 158
drwxr-xr-x   6 u111111  u111111    8 Jun 12 19:36 .
dr-x--x--x  11 root     wheel     11 Jun 11 17:31 ..
-rw-r--r--   1 u111111  u111111  158 Jun 12 19:49 .hsh_history
drwx------   2 u111111  u111111    4 Nov 15  2021 .ssh
drwxrwxr-x   5 u111111  u111111    5 May 30  2021 backup
```

`hsbt mount -i myBox1 -l /mnt/hetzner/mybox`
# hetzner-storage-box-tool
Collection of scripts wrapped into a CLI-bash-tool for common tasks with a hetzner storage box written in python

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

**(This is just a documention preview. Package is not yet usabe)**

`hsbt --help`

## Create connection

`hsbt setConnection -i myBox1 -u u111111 -h u111111.your-storage.de -o`

```bash
Directory to store ssh private and public key [~/.ssh/]: ↩️
Saved connection at '/home/tim/.config/hetzner_sb_connections.json' as:
        identifier='myBox1' host='u111111.your-storage.de' user='u111111' key_dir='~/.ssh/'
```

## use connection

`hsbt remoteSSH -i myBox1 "ls -la"`

`hsbt mount -i myBox1 -l /mnt/hetzner/mybox`
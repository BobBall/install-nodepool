# install-nodepool

Scripts to install nodepool and OSCI, the XenServer OpenStack CI.

## Installation

Use pip to install this software package. As an example, if you have this
directory cloned to `~/src/install-nodepool` then:

    pip install ~/somedir

Alternatively you can install directly from github, for example to install
the `2014-11` branch:

    pip install git+git://github.com/citrix-openstack/install-nodepool.git@2014-11

## Usage

To demonstrate an example installation, a VM will be used. This VM is
accessible on port `2424` on the host `localhost`. It's actually a VM having
its ssh port forwarded there. The user/password combo is `ubuntu/ubuntu`. The
VM is running **Ubuntu 14.04.1 LTS**.

Now you need to create a key to be used to communicate with the box:

    ssh-keygen -f ubuntu.key -N "" -C "osci-controller"

And another one to be used by nodepool:

    ssh-keygen -f nodepool.key -N "" -C "osci-nodepool"

And one to be used by jenkins:

    ssh-keygen -f jenkins.key -N "" -C "osci-jenkins"

To enable passwordless authentication to the new system, load an agent and add
the key:

    eval $(ssh-agent)
    ssh-add ubuntu.key

And enable authentication to the system:

    cat ubuntu.key.pub |
        ssh -p 2424 ubuntu@localhost "mkdir .ssh && dd of=.ssh/authorized_keys"

The following command should not ask for a password:

    ssh -p 2424 ubuntu@localhost "ls -la"

### Install nodepool

To install nodepool (but not to start it yet!), you should do the following:

    inp-nodepool-install --port 2424 ubuntu 127.0.0.1

After this operation, nodepool is installed to the controller. To understand
what has happened, take a look at [installscript.sh](inp/installscript.sh).

### Configure nodepool

Next phase to configure the instance. This includes specifying the key files to
be used, and an image name that will be used. As the nodepool config file
needs your cloud credentials, you also have to specify an openrc file. This
file could be downloaded from rackspace once you're logged in. You will also
need to specify the password for your rackspace account.

    inp-nodepool-configure --port 2424 ubuntu 127.0.0.1 openrc DEMO \
        nodepool.key jenkins.key rspass

Please note, that you can also specify `--min-ready` to specify the number of
nodes to be baked. For demo purposes you might want to specify it as `1`.

To understand what has happened, take a look at
[nodepool_config.sh](inp/nodepool_config.sh).

### Set up cloud keys

Now nodepool is configured, you need to upload your key to be used to the
cloud so that you can communicate with the instances launched:

    inp-upload-keys ubuntu 127.0.0.1 openrc --port=2424

By default it will not update your keys, so if you have existing keys, it will
fail. To remove the existing keys, specify `--remove`.

The VM is ready to be used.

### Install osci

OSCI is playing the role of jenkins. This component is responsible for many
things, including:
  - watching the gerrit stream for review requests
  - starting tests
  - uploading logs

To install osci, use the following command:

    inp-osci-install --port 2424 citrix_gerrit ubuntu 127.0.0.1 SWIFT_KEY DEMO

Where `SWIFT_KEY` will be used to upload the logs to swift, and `DEMO` is the
image name to be used.

### Update osci binaries

To update the binaries, use the following command:

    inp-osci-update --port 2424 ubuntu 127.0.0.1

### Backup databases

To save a backup of all the databases to the file `backup.tgz`:

    inp-osci-backup --port 2424 ubuntu 127.0.0.1 backup.tgz

### Restore database

To restore the database from the local file `backup.tgz`, use:

    inp-osci-restore --port 2424 ubuntu 127.0.0.1 backup.tgz

### Development: Update nodepool

If you wanted to update the version of nodepool that you are running, update
it with:

    inp-nodepool-update --port 2424 ubuntu 127.0.0.1

Use `--nodepool_repo` and `--nodepool_branch` to specify the target version.

### Status of the CI

To get a status of the CI, use:

    inp-osci-status --port 2424 ubuntu 127.0.0.1

Please note, that you can use the `--service` switch to ask for the status of
an individual service.

### Start Services

Start is similar to status, as it also has the `--service` switch.

    inp-osci-start --port 2424 ubuntu 127.0.0.1

### Stop Nodepool

To stop services:

    inp-osci-stop --port 2424 ubuntu 127.0.0.1

## Useful commands

This section shows what commands could be used inside the VM that has been
installed.

### Generating an image

A wrapper script is generated during the configure phase which allows you to
invoke nodepool. The wrapper script also exports a `NODEPOOL_SSH_KEY` variable
to the process. Environment variables starting sith `NODEPOOL_` are injected
to the environment of the node installation scripts.

To update an image in `rax-iad` region:

    osci-nodepool image-update rax-iad DEMO

### Checking osci's connection to an instance

This command requires that you already created a node with nodepool. Once
`osci-nodepool list` returns with an IP address, you can try to connect to
that with:

    sudo -u osci -i
    . /opt/osci/env/bin/activate
    osci-check-connection exec 162.242.252.142

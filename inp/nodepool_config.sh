#!/bin/bash
set -eux

THIS_FILE=$(readlink -f $0)
THIS_DIR=$(dirname $THIS_FILE)

. $THIS_DIR/functions.sh

NODEPOOL_XENSERVER_XVA_URL="http://downloads.vmd.citrix.com/OpenStack/xenapi-in-the-cloud-appliances/prod_ci"
NODEPOOL_XENSERVER_ISO_URL="http://b689e986177cd5e95fdc-f25477f50b352a719ae4146d83171f6e.r30.cf5.rackcdn.com/xenserver65/results.html"


######
# Clone project-config
sudo rm -rf /opt/nodepool/project-config
get_project_config

######
# Make sure scripts dir exists
test -d /opt/nodepool/project-config/nodepool/scripts


source $THIS_DIR/nodepool_rewrite_config.sh


######
# Copy ssh settings
sudo rm -rf $NODEPOOL_HOME_DIR/.ssh
sudo mkdir $NODEPOOL_HOME_DIR/.ssh

sudo cp $THIS_DIR/nodepool.priv $NODEPOOL_HOME_DIR/.ssh/id_rsa
sudo cp $THIS_DIR/jenkins.priv $NODEPOOL_HOME_DIR/.ssh/jenkins


######
# Configure logging
sudo tee /etc/nodepool/logging.conf << EOF
[loggers]
keys=root,nodepool,requests,image

[handlers]
keys=console,debug,normal,image

[formatters]
keys=simple

[logger_root]
level=WARNING
handlers=console

[logger_requests]
level=WARNING
handlers=debug,normal
qualname=requests

[logger_nodepool]
level=DEBUG
handlers=debug,normal
qualname=nodepool

[logger_image]
level=INFO
handlers=image
qualname=nodepool.image.build
propagate=0

[handler_console]
level=WARNING
class=StreamHandler
formatter=simple
args=(sys.stdout,)

[handler_debug]
level=DEBUG
class=logging.handlers.TimedRotatingFileHandler
formatter=simple
args=('/var/log/nodepool/debug.log', 'midnight', 1, 30,)

[handler_normal]
level=INFO
class=logging.handlers.TimedRotatingFileHandler
formatter=simple
args=('/var/log/nodepool/nodepool.log', 'midnight', 1, 30,)

[handler_image]
level=INFO
class=logging.handlers.TimedRotatingFileHandler
formatter=simple
args=('/var/log/nodepool/image.log', 'midnight', 1, 30,)

[formatter_simple]
format=%(asctime)s %(levelname)s %(name)s: %(message)s
datefmt=
EOF



######
# Add startup script
sudo tee /etc/init/nodepool.conf << NODEPOOLSTARTER
start on runlevel [2345]
stop on runlevel [016]

setuid $NODEPOOL_USER

chdir $NODEPOOL_HOME_DIR

script
    export NODEPOOL_SSH_KEY="\$(cat $NODEPOOL_HOME_DIR/.ssh/jenkins.pub | cut -d' ' -f 2)"
    export NODEPOOL_PYPI_MIRROR="http://pypi.python.org/simple"
    export NODEPOOL_XENSERVER_XVA_URL=$NODEPOOL_XENSERVER_XVA_URL
    export NODEPOOL_XENSERVER_ISO_URL=$NODEPOOL_XENSERVER_ISO_URL
    /opt/nodepool/env/bin/python \\
        /opt/nodepool/env/bin/nodepoold \\
        -l /etc/nodepool/logging.conf \\
        -d
end script
NODEPOOLSTARTER

sudo chown -R $NODEPOOL_USER:$NODEPOOL_USER $NODEPOOL_HOME_DIR/.ssh
sudo chmod -R g-w,g-r,o-w,o-r $NODEPOOL_HOME_DIR/.ssh
sudo chmod -R g-w,o-w /etc/nodepool /opt/nodepool
sudo chown -R $NODEPOOL_USER:nogroup /var/log/nodepool
sudo chmod -R g-w,o-w /var/log/nodepool


######
# Generate public keys
sudo -u $NODEPOOL_USER bash -c "\
    ssh-keygen -y -f $NODEPOOL_HOME_DIR/.ssh/jenkins > $NODEPOOL_HOME_DIR/.ssh/jenkins.pub"
sudo -u $NODEPOOL_USER bash -c "\
    ssh-keygen -y -f $NODEPOOL_HOME_DIR/.ssh/id_rsa > $NODEPOOL_HOME_DIR/.ssh/id_rsa.pub"


######
# Create a management script
sudo tee /usr/local/bin/osci-nodepool << EOF
#!/bin/bash
sudo -u $NODEPOOL_USER -i \\
    NODEPOOL_SSH_KEY="\$(cat $NODEPOOL_HOME_DIR/.ssh/jenkins.pub | cut -d' ' -f 2)" \\
    NODEPOOL_PYPI_MIRROR="http://pypi.python.org/simple" \\
    NODEPOOL_XENSERVER_XVA_URL=$NODEPOOL_XENSERVER_XVA_URL \\
    NODEPOOL_XENSERVER_ISO_URL=$NODEPOOL_XENSERVER_ISO_URL \\
    /opt/nodepool/env/bin/nodepool "\$@"
EOF

sudo chmod 0755 /usr/local/bin/osci-nodepool

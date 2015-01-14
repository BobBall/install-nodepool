set -eux

THIS_FILE=$(readlink -f $0)
THIS_DIR=$(dirname $THIS_FILE)

. $THIS_DIR/functions.sh

######
# Install system level dependencies
sudo apt-get -qy update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -qy \
    git mysql-server libmysqlclient-dev g++ python-dev libzmq-dev \
    python-pip python-virtualenv \
    gearman-job-server libffi-dev libssl-dev < /dev/null


######
# Create a nodepool user
getent passwd $NODEPOOL_USER || sudo adduser \
    --home $NODEPOOL_HOME_DIR \
    --disabled-password \
    --quiet \
    --gecos $NODEPOOL_USER \
    $NODEPOOL_USER


######
# Create install directory
sudo mkdir -p /opt/nodepool


######
# Create config directory
sudo mkdir -p /etc/nodepool


######
# Create pid directory
sudo mkdir -p /var/run/nodepool


######
# Create log directory
sudo mkdir -p /var/log/nodepool


######
# Check out sources
sudo mkdir -p /opt/nodepool/src
get_nodepool_sources


######
# Install binaries
sudo virtualenv /opt/nodepool/env
sudo bash << EOF
set -ex
. /opt/nodepool/env/bin/activate
set -u
cd /opt/nodepool/src
pip install -U distribute
pip install -U -r requirements.txt
pip install .
pip install python-novaclient rackspace-auth-openstack
EOF


######
# Create database
mysql -u root << DBINIT
create database if not exist nodepool;
GRANT ALL ON nodepool.* TO 'nodepool'@'localhost';
flush privileges;
DBINIT

######
# Set rights
sudo chmod -R g-w,o-w /etc/nodepool /opt/nodepool
sudo chown -R $NODEPOOL_USER:nogroup /var/log/nodepool /var/run/nodepool
sudo chmod -R g-w,o-w /var/log/nodepool /var/run/nodepool

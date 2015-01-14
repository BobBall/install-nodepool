set -eux

THIS_FILE=$(readlink -f $0)
THIS_DIR=$(dirname $THIS_FILE)

. $THIS_DIR/functions.sh

######
# Create an osci user
getent passwd $OSCI_USER || sudo adduser \
    --home $OSCI_HOME_DIR \
    --disabled-password \
    --quiet \
    --gecos $OSCI_USER \
    $OSCI_USER


######
# Create install directory
sudo mkdir -p /opt/osci


######
# Create config directory
sudo mkdir -p /etc/osci


######
# Create pid directory
sudo mkdir -p /var/run/osci


######
# Create log directory
sudo mkdir -p /var/log/osci


######
# Check out sources
sudo mkdir -p /opt/osci/src
get_osci_sources

######
# Create database
mysql -u root << DBINIT
create database if not exists openstack_ci;
GRANT ALL ON openstack_ci.* TO 'nodepool'@'localhost';
flush privileges;
DBINIT


SOURCE_ENV=". /opt/osci/env/bin/activate"

######
# Install binaries
sudo virtualenv /opt/osci/env
sudo bash << EOF
set -ex
. /opt/osci/env/bin/activate
set -u
cd /opt/nodepool/src
pip install -U -r requirements.txt
pip install .

cd /opt/osci/src
pip install -U -r requirements.txt
pip install .

pip install -U requests==2.2.0
EOF


######
# Set rights
sudo chmod -R g-w,o-w /etc/osci /opt/osci
sudo chown -R $OSCI_USER:nogroup /var/log/osci /var/run/osci
sudo chmod -R g-w,o-w /var/log/osci /var/run/osci

######
# Create Database Schema
sudo -u $OSCI_USER -i bash -c "$SOURCE_ENV ; osci-create-dbschema"


sudo tee /etc/init/citrix-ci.conf << CITRIXCISTARTER
start on runlevel [2345]
stop on runlevel [016]

respawn
respawn limit 3 60

setuid $OSCI_USER
chdir $OSCI_HOME_DIR

script
    $SOURCE_ENV && osci-manage -v \\
    >> /var/log/osci/citrix-ci.log 2>&1
end script
CITRIXCISTARTER

sudo tee /etc/init/citrix-ci-gerritwatch.conf << GERRITWATCH
start on runlevel [2345]
stop on runlevel [016]

respawn
respawn limit 3 60

setuid $OSCI_USER
chdir $OSCI_HOME_DIR

script
    $SOURCE_ENV && osci-watch-gerrit \\
    >> /var/log/osci/citrix-ci-gerritwatch.log 2>&1
end script

post-stop exec sleep 10
GERRITWATCH


######
# Copy ssh settings
sudo rm -rf $OSCI_HOME_DIR/.ssh
sudo mkdir -p $OSCI_HOME_DIR/.ssh

sudo cp $NODEPOOL_HOME_DIR/.ssh/jenkins $OSCI_HOME_DIR/.ssh/jenkins
sudo cp $THIS_DIR/gerrit.key $OSCI_HOME_DIR/.ssh/id_rsa
sudo chown -R $OSCI_USER:$OSCI_USER $OSCI_HOME_DIR/.ssh
sudo chmod -R g-w,g-r,o-w,o-r $OSCI_HOME_DIR/.ssh

source $THIS_DIR/osci_rewrite_config.sh

######
# Add gerrit to known hosts:
sudo -u osci -i /bin/bash -c "ssh-keyscan -H -t rsa -p $GERRIT_PORT '$GERRIT_HOST [$GERRIT_HOST]:$GERRIT_PORT'> ~/.ssh/known_hosts"

######
# Create a link for osci-view
sudo ln -s -t /usr/local/bin /opt/osci/env/bin/osci-view

######
# Create osci-manage
rm -f /usr/local/bin/osci-manage
sudo tee /usr/local/bin/osci-manage << EOF
#!/bin/bash
sudo -u $OSCI_USER -i /opt/osci/env/bin/osci-manage "\$@"
EOF
sudo chmod 0755 /usr/local/bin/osci-manage


######
# Skip uploading status for now
sudo touch /etc/osci/skip_status_update

######
# Schedule status upload
sudo crontab -u $OSCI_USER - <<EOF
*/10 * * * * /opt/osci/src/upload_ci_status.sh >> /var/log/osci/status_upload.log 2>&1
EOF

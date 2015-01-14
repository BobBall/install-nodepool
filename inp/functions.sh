function get_nodepool_sources() {
    [ -e /opt/nodepool/src ] || sudo git clone \
        --quiet \
        $NODEPOOL_REPO /opt/nodepool/src
    pushd /opt/nodepool/src
    git remote update
    git checkout $NODEPOOL_BRANCH
    popd
}


function get_osci_sources() {
    [ -e /opt/osci/src ] || sudo git clone \
        --quiet \
        $OSCI_REPO /opt/osci/src
    pushd /opt/osci/src
    git remote update
    git checkout $OSCI_BRANCH
    popd
}


function get_project_config() {
    [ -e /opt/nodepool/project-config ] || sudo git clone --quiet \
        $PROJECT_CONFIG_URL /opt/nodepool/project-config
    pushd /opt/nodepool/project-config
    git remote update
    git checkout $PROJECT_CONFIG_BRANCH
    popd
}

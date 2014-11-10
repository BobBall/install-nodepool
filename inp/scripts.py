import argparse
import StringIO
import logging
import yaml

from inp import remote
from inp import data
from inp import bash_env
from inp import templating
from inp.validation import file_access_issues, remote_system_access_issues, get_args_or_die, die_if_issues_found


DEFAULT_NODEPOOL_REPO = 'https://github.com/citrix-openstack/nodepool.git'
DEFAULT_NODEPOOL_BRANCH = 'master'
DEFAULT_PORT = 22
DEFAULT_MIN_READY = 8


def bashline(some_dict):
    return ' '.join('{key}={value}'.format(key=key, value=value) for
        key, value in some_dict.iteritems())


class NodepoolEnv(object):
    def __init__(self):
        self.username = 'nodepool'
        self.home = '/home/nodepool'
        self.key_name = 'nodepool'

    @property
    def _env_dict(self):
        return dict(
            NODEPOOL_USER=self.username,
            NODEPOOL_HOME_DIR=self.home,
        )

    @property
    def bashline(self):
        return bashline(self._env_dict)

    def as_dict(self):
        return self._env_dict


class NodepoolInstallEnv(NodepoolEnv):
    def __init__(self, repo, branch):
        super(NodepoolInstallEnv, self).__init__()
        self.repo = repo
        self.branch = branch

    @property
    def _env_dict(self):
        env = super(NodepoolInstallEnv, self)._env_dict
        return dict(
            env,
            NODEPOOL_REPO=self.repo,
            NODEPOOL_BRANCH=self.branch,
        )


class NodepoolConfigEnv(NodepoolEnv):

    def __init__(self, openrc, image_name, min_ready, rackspace_password):
        super(NodepoolConfigEnv, self).__init__()
        self.project_config_url = (
            'https://github.com/citrix-openstack/project-config')
        self.project_config_branch = 'xenserver-ci'
        self.openrc = openrc
        self.image_name = image_name
        self.min_ready = str(min_ready)
        self.rackspace_password = rackspace_password

    @property
    def _env_dict(self):
        env = super(NodepoolConfigEnv, self)._env_dict
        return dict(
            env,
            PROJECT_CONFIG_URL=self.project_config_url,
            PROJECT_CONFIG_BRANCH=self.project_config_branch,
            IMAGE_NAME=self.image_name,
            MIN_READY=self.min_ready,
            RACKSPACE_PASSWORD=self.rackspace_password,
            **self.openrc
        )


def parse_install_args():
    parser = argparse.ArgumentParser(description="Install Nodepool")
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help='SSH port to use (default: %s)' % DEFAULT_PORT
    )
    parser.add_argument(
        '--nodepool_repo',
        default=DEFAULT_NODEPOOL_REPO,
        help='Nodepool repository (default: %s)' % DEFAULT_NODEPOOL_REPO,
    )
    parser.add_argument(
        '--nodepool_branch',
        default='master',
        help='Nodepool branch (default: %s)' % DEFAULT_NODEPOOL_BRANCH,
    )
    return parser.parse_args()


def issues_for_install_args(args):
    return remote_system_access_issues(args.username, args.host, args.port)


def pubkey_for(privkey):
    return privkey + '.pub'


def get_params_or_die(cloud_parameters_file):
    with open(cloud_parameters_file, 'rb') as pfile:
        parameter_lines = pfile.read()
        pfile.close()

    die_if_issues_found(bash_env.bash_env_parsing_issues(parameter_lines))
    return bash_env.bash_to_dict(parameter_lines)


def install():
    args = get_args_or_die(parse_install_args, issues_for_install_args)

    env = NodepoolInstallEnv(args.nodepool_repo, args.nodepool_branch)

    with remote.connect(args.username, args.host, args.port) as connection:
        connection.put(data.install_script('installscript.sh'), 'install.sh')
        connection.run('%s bash install.sh' % env.bashline)
        connection.run('rm -f install.sh')


class NovaCommands(object):
    def __init__(self, config_env):
        self.config_env = config_env

    def _nova_cmd(self, region, cmd):
        env = self.config_env

        nova_env = dict(env.openrc, OS_REGION_NAME=region)
        return 'sudo -u {user} /bin/sh -c "HOME={home} {nova_env} /opt/nodepool/env/bin/nova {cmd}"'.format(
            user=env.username,
            nova_env=bashline(nova_env),
            home=env.home,
            cmd=cmd,
            region=region,
        )

    def keypair_show(self, region, name):
        return self._nova_cmd(region, 'keypair-show {name}'.format(name=name))

    def keypair_delete(self, region, name):
        return self._nova_cmd(region, 'keypair-delete {name}'.format(name=name))

    def keypair_add(self, region, name, path):
        return self._nova_cmd(
            region, 'keypair-add --pub-key {path} {name}'.format(
                name=name,
                path=path
            )
        )


def image_provider_regions():
    nodepool_config = yaml.load(data.nodepool_config(dict()))

    used_providers = []
    for target in nodepool_config['targets']:
        for image in target['images']:
            for provider in image['providers']:
                used_providers.append(provider['name'])

    regions = []
    for provider in nodepool_config['providers']:
        if provider['name'] in used_providers:
            regions.append(provider['region-name'])

    return regions


def _parse_nodepool_configure_args():
    parser = argparse.ArgumentParser(
        description="Configure Nodepool on a remote machine")
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    parser.add_argument('openrc', help='OpenRc file to access the cloud')
    parser.add_argument('image_name', help='Image name to be used')
    parser.add_argument('nodepool_keyfile', help='SSH key to be used to prepare nodes')
    parser.add_argument('jenkins_keyfile', help='SSH key to be used by jenkins')
    parser.add_argument('rackspace_password', help='Rackspace password')
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help='SSH port to use (default: %s)' % DEFAULT_PORT
    )
    parser.add_argument(
        '--min_ready',
        type=int,
        default=DEFAULT_MIN_READY,
        help='Default number of min ready nodes (default: %s)' % DEFAULT_MIN_READY
    )
    return parser.parse_args()


def _issues_for_nodepool_configure_args(args):
    return (
        remote_system_access_issues(args.username, args.host, args.port)
        + file_access_issues(args.openrc)
        + file_access_issues(args.nodepool_keyfile)
        + file_access_issues(args.jenkins_keyfile)
    )


def nodepool_configure():
    args = get_args_or_die(
        _parse_nodepool_configure_args,
        _issues_for_nodepool_configure_args
    )

    env = NodepoolConfigEnv(
        get_params_or_die(args.openrc),
        args.image_name,
        args.min_ready,
        args.rackspace_password,
    )
    nodepool_config_file = data.nodepool_config(env.as_dict())

    with remote.connect(args.username, args.host, args.port) as connection:
        connection.put(
            data.install_script('nodepool_config.sh'),
            'nodepool_config.sh'
        )
        connection.put(
            nodepool_config_file,
            'nodepool.yaml'
        )

        connection.put(
            args.nodepool_keyfile,
            'nodepool.priv'
        )

        connection.put(
            args.jenkins_keyfile,
            'jenkins.priv'
        )

        connection.run('%s bash nodepool_config.sh' % env.bashline)

        connection.run('rm -f nodepool_config.sh')
        connection.run('rm -f nodepool.yaml')
        connection.run('rm -f nodepool.priv')
        connection.run('rm -f jenkins.priv')


def parse_start_args():
    parser = argparse.ArgumentParser(description="Start Nodepool")
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    return parser.parse_args()


def issues_for_start_args(args):
    issues = remote_system_access_issues(args.username, args.host, args.port)
    return issues


def start():
    args = get_args_or_die(parse_start_args, issues_for_start_args)

    with remote.connect(args.username, args.host) as connection:
        connection.sudo('service nodepool start')


def parse_osci_install_args():
    parser = argparse.ArgumentParser(description="Install OSCI")
    parser.add_argument('private_key', help='Private key file')
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    parser.add_argument('params', help='OSCI settings file')
    parser.add_argument('--image_name', default='xsdsvm', help='Image name to use')
    parser.add_argument('--osci_repo',
                        default='https://github.com/citrix-openstack/openstack-citrix-ci.git',
                        help='OSCI repository')
    parser.add_argument('--osci_branch',
                        default='master',
                        help='Nodepool branch')
    return parser.parse_args()


def issues_for_osci_install_args(args):
    issues = (
        file_access_issues(args.private_key)
        + file_access_issues(pubkey_for(args.private_key))
        + remote_system_access_issues(args.username, args.host, args.port)
    )

    return issues


def osci_install():
    args = get_args_or_die(parse_osci_install_args, issues_for_osci_install_args)

    with remote.connect(args.username, args.host) as connection:
        connection.put(args.private_key, '.ssh/citrix_gerrit')
        connection.put(pubkey_for(args.private_key), '.ssh/citrix_gerrit.pub')
        connection.run('chmod 0400 .ssh/citrix_gerrit')
        connection.put(args.params, 'osci.config')
        connection.put(data.install_script('osci_installscript.sh'), 'osci_installscript.sh')
        connection.run('bash osci_installscript.sh "%s" "%s"' %
                       (args.osci_repo, args.osci_branch))


def parse_osci_start_args():
    parser = argparse.ArgumentParser(description="Start OSCI")
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    return parser.parse_args()


def issues_for_osci_start_args(args):
    issues = remote_system_access_issues(args.username, args.host, args.port)
    return issues


def osci_start():
    args = get_args_or_die(parse_osci_start_args, issues_for_osci_start_args)

    with remote.connect(args.username, args.host) as connection:
        connection.sudo('service citrix-ci start')
        connection.sudo('service citrix-ci-gerritwatch start')


def _parse_nodepool_upload_keys_args():
    parser = argparse.ArgumentParser(
        description="Upload a key to the cloud")
    parser.add_argument('username', help='Username to target host')
    parser.add_argument('host', help='Target host')
    parser.add_argument('openrc', help='OpenRc file to access the cloud')
    parser.add_argument(
        '--remove',
        action="store_true",
        default=False,
        help='OpenRc file to access the cloud'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help='SSH port to use (default: %s)' % DEFAULT_PORT
    )
    return parser.parse_args()


def _issues_for_nodepool_upload_keys_args(args):
    return (
        remote_system_access_issues(args.username, args.host, args.port)
        + file_access_issues(args.openrc)
    )


def nodepool_upload_keys():
    args = get_args_or_die(
        _parse_nodepool_upload_keys_args,
        _issues_for_nodepool_upload_keys_args
    )

    env = NodepoolConfigEnv(
        get_params_or_die(args.openrc),
        'ignored',
        'ignored',
        'ignored',
    )
    nodepool_config_file = data.nodepool_config(env.as_dict())
    nova_commands = NovaCommands(env)

    regions = image_provider_regions()

    with remote.connect(args.username, args.host, args.port) as connection:
        key_exists_in_regions = []
        for region in regions:
            result = connection.run(
                nova_commands.keypair_show(region, env.key_name),
                ignore_failures=True,
            )
            if result.succeeded:
                key_exists_in_regions.append(region)

        if key_exists_in_regions and not args.remove:
            raise SystemExit(
                'Keypair "{keypair}" already exists at regions: {regions}'
                ' Please remove them manually or use --remove'.format(
                    keypair=env.key_name,
                    regions=','.join(key_exists_in_regions)
                )
            )

        if args.remove:
            for region in key_exists_in_regions:
                connection.run(
                    nova_commands.keypair_delete(region, env.key_name)
                )

        for region in regions:
            result = connection.run(
                nova_commands.keypair_add(
                    region,
                    env.key_name,
                    '{home}/.ssh/id_rsa.pub'.format(home=env.home))
            )

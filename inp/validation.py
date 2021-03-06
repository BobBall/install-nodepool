import os
import sys
from inp import remote


def message_for_first_issue(checks):
    for check, msg in checks:
        if check() is False:
            return [msg]
    return []


def file_access_issues(fpath):
    checks = [
        (lambda: os.path.exists(fpath), 'File %s does not exist' % fpath),
        (lambda: os.path.isfile(fpath), 'File %s is not a file' % fpath),
    ]
    return message_for_first_issue(checks)


def remote_system_access_issues(username, host, port):
    checks = [
        (lambda: remote.check_connection(username, host, port),
            'Cannot connect to %s:%s using %s' % (host, port, username)),
        (lambda: remote.check_sudo(username, host, port),
            'Cannot sudo on %s:%s as %s' % (host, port, username))
    ]
    return message_for_first_issue(checks)


def get_args_or_die(arg_parser, arg_validator):
    args = arg_parser()
    issues = arg_validator(args)
    die_if_issues_found(issues)
    return args


def die_if_issues_found(issues):
    if issues:
        for issue in issues:
            sys.stderr.write('ERROR: ' + issue + '\n')
        sys.exit(1)

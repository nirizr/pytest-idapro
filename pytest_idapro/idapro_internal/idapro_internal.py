import idc

try:  # python3
    from multiprocessing.connection import Connection
except ImportError:  # python2
    from _multiprocessing import Connection


import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pytest-idapro.internal.worker')

command_handlers = {}


def command_handler(cmd):
    command_prefix, command_name = cmd.__name__.split("_", 1)
    assert command_prefix == "command"
    command_handlers[command_name] = cmd
    return cmd


def handle_prerequisites():
    # test pytest is installed, otherwise attempt installing
    try:
        import pytest
        del pytest
        return True
    except ImportError:
        pass

    try:
        import pip
    except ImportError:
        log.critical("Both pytest and pip are missing from IDA environment, "
                     "execution inside IDA is impossible.")
        return False

    # handle different versions of pip
    try:
        from pip import main as pip_main
    except ImportError:
        # here be dragons
        from pip._internal import main as pip_main

    # ignoring installed six and upgrading is requried to avoid an osx bug
    # see https://github.com/pypa/pip/issues/3165 for more details
    pip_command = ['install', 'pytest']
    if 'osx' == 'osx':
        pip_command += ['--upgrade', '--user', '--ignore-installed', 'six']
    pip_main(pip_command)

    try:
        import pytest
        del pytest
    except ImportError:
        log.exception("pytest module unavailable after installation attempt, "
                      "cannot proceed.")
        return False

    return True


@command_handler
def command_ping(args):
    return "pong"


@command_handler
def command_quit(args):
    global stop
    stop = True
    return "quitting"


def handle_command(command_line):
    command_args = command_line.split()
    command = command_args.pop()

    if command not in command_handlers:
        raise RuntimeError("Unrecognized command recieved: "
                           "'{}'".format(command))
    log.debug("Received command: {}".format(command_line))
    command_handler = command_handlers[command]
    response = command_handler(command_args)
    log.debug("Responding: {}".format(response))
    return response


stop = False


def handle_communication(conn):
    global stop
    try:
        while not stop:
            command_line = conn.recv()
            response = handle_command(command_line)
            conn.send(response)
    except RuntimeError:
        log.exception("Runtime error encountered during message handling")
    except EOFError:
        log.info("remote connection closed abruptly, terminating.")


def main():
    if not handle_prerequisites():
        return

    conn = Connection(int(idc.ARGV[1]))

    # TODO: run this in a new thread
    handle_communication(conn)


if __name__ == '__main__':
    # TODO: wait until auto-analysis is done
    main()
    # TODO: quit IDA

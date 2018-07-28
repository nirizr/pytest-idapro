import idc

try:  # python3
    from multiprocessing.connection import Connection
except ImportError:  # python2
    from _multiprocessing import Connection


def handle_prerequisites():
    # test pytest is installed, other-wise attempt installing
    try:
        import pytest
        return True
    except ImportError:
        pass

    try:
        import pip
    except ImportError:
        print("Both pytest and pip are missing from IDA environment, "
              "execution inside IDA is impossible.")
        raise

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
    # TODO: OSX FIX: to get this working, add --user path to sys.path


def main():
    handle_prerequisites()

    recv = Connection(int(idc.ARGV[1]))
    send = Connection(int(idc.ARGV[2]))

    for i in range(5):
        if recv.poll(1):
            r = recv.recv()
            print("RECV: " + r)


if __name__ == '__main__':
    main()

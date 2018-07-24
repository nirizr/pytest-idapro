import idc

try:  # python3
    from multiprocessing.connection import Connection
except ImportError:  # python2
    from _multiprocessing import Connection


def main():
    recv = Connection(int(idc.ARGV[1]))
    send = Connection(int(idc.ARGV[2]))

    for i in range(5):
        if recv.poll(1):
            r = recv.recv()
            print("RECV: " + r)


if __name__ == '__main__':
    main()

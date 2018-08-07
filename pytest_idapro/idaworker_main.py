import idaapi
import idc

import os
import sys

from .idapro_internal import idaworker


def main():
    sys.path.append(os.getcwd())
    sys.path.append(os.path.dirname(__file__))

    # TODO: use idc.ARGV with some option parsing package
    worker = idaworker.IdaWorker(idc.ARGV[1])
    worker.run()
    idaapi.qexit(0)


if __name__ == '__main__':
    main()

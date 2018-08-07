import idaapi
import idc

import os
import sys

sys.path.append(os.path.dirname(__file__))

from idapro_internal import idaworker  # noqa: E402


def main():
    # TODO: use idc.ARGV with some option parsing package
    worker = idaworker.IdaWorker(idc.ARGV[1])
    worker.run()
    idaapi.qexit(0)


if __name__ == '__main__':
    main()

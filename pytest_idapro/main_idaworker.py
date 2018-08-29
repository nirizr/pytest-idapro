import idaapi
import idc

try:
    from idapro_internal import idaworker
except ImportError:
    from .idapro_internal import idaworker


def main():
    # TODO: use idc.ARGV with some option parsing package
    worker = idaworker.IdaWorker(idc.ARGV[1])
    should_quit = worker.run()
    if should_quit:
        idaapi.qexit(0)


if __name__ == '__main__':
    main()

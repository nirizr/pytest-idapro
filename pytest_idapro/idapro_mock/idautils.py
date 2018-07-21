#---------------------------------------------------------------------
# IDAPython - Python plugin for Interactive Disassembler
#
# Copyright (c) 2004-2010 Gergely Erdelyi <gergely.erdelyi@d-dome.net>
#
# All rights reserved.
#
# For detailed copyright information see the file COPYING in
# the root of the distribution archive.
#---------------------------------------------------------------------
# flake8: noqa
"""
idautils.py - High level utility functions for IDA
"""
from . import ida_funcs
from . import ida_ida


def Functions(start=None, end=None):
    """
    Get a list of functions

    @param start: start address (default: inf.minEA)
    @param end:   end address (default: inf.maxEA)

    @return: list of heads between start and end

    @note: The last function that starts before 'end' is included even
    if it extends beyond 'end'. Any function that has its chunks scattered
    in multiple segments will be reported multiple times, once in each segment
    as they are listed.
    """
    if not start: start = ida_ida.cvar.inf.minEA
    if not end:   end = ida_ida.cvar.inf.maxEA

    # find first function head chunk in the range
    chunk = ida_funcs.get_fchunk(start)
    if not chunk:
        chunk = ida_funcs.get_next_fchunk(start)
    while chunk and chunk.startEA < end and (chunk.flags & ida_funcs.FUNC_TAIL) != 0:
        chunk = ida_funcs.get_next_fchunk(chunk.startEA)
    func = chunk

    while func and func.startEA < end:
        startea = func.startEA
        yield startea
        func = ida_funcs.get_next_func(startea)


def Chunks(start):
    """
    Get a list of function chunks

    @param start: address of the function

    @return: list of funcion chunks (tuples of the form (start_ea, end_ea))
             belonging to the function
    """
    func_iter = ida_funcs.func_tail_iterator_t( ida_funcs.get_func( start ) )
    status = func_iter.main()
    while status:
        chunk = func_iter.chunk()
        yield (chunk.startEA, chunk.endEA)
        status = func_iter.next()

oga = object.__getattribute__
osa = object.__setattr__


def clean_arg(arg):
    """Cleanup argument's representation for comparison by removing the
    terminating memory address"""

    sarg = repr(arg)
    if sarg[0] != '<':
        return arg

    if len(sarg.split()) < 2:
        return arg

    parts = sarg.split()
    if parts[-2] == 'at' and parts[-1][-1] == '>' and parts[-1][:2] == '0x':
        return " ".join(parts[:-2]) + '>'

    return arg

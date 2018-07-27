import tempfile


tempidadir = None


def GetIdaDirectory():
    global tempidadir
    if not tempidadir:
        tempidadir = tempfile.mkdtemp("idadir")
    return tempidadir


def GetIdbPath():
    return "./fake-idb-file.idb"


def GetInputFile():
    return "./fake-input-file.exe"


def GetInputMD5():
    return "\xff" * 32


ARGV = ['./fake-script-file.py']

import tempfile


tempidadir = None


def GetIdaDirectory():
    global tempidadir
    if not tempidadir:
        tempidadir = tempfile.mkdtemp("idadir")
    return tempidadir


def GetIdbPath():
    return "./file.idb"

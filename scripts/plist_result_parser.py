import plistlib


class Location:
    def __init__(self, file_name, row, col):
        self.filename = file_name
        self.row = row
        self.col = col


class Warning:
    def __init__(self, msg, loc):
        self.message = msg
        self.location = loc

    def on_same_line(self, other):
        return self.location.row == other.location.row


def warnings_from_plist(plist_file):
    """Parse a plist file and return the warnings"""
    raise NotImplementedError
    # res = Warning("dummy", Location("dummyfile", -1, -1))
    # return res


def is_potential_duplicate(w1, w2):
    return w1.on_same_line(w2)

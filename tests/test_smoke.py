import sys


def test_version_de_python():
    assert sys.version_info >= (3, 12), "El proyecto pide Python 3.12 o superior"

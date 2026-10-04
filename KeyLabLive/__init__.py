from __future__ import absolute_import, print_function, unicode_literals

from .keylab_live import KeyLabLive


def create_instance(c_instance):
    return KeyLabLive(c_instance)

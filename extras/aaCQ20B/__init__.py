from .cq20b_bridge import CQ20BBridge


def create_instance(c_instance):
    return CQ20BBridge(c_instance)

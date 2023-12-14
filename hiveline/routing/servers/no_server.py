from hiveline.routing.servers.routing_server import RoutingServer


class NoServer(RoutingServer):
    def __init__(self):
        pass

    def build(self, config, force_rebuild=False):
        pass

    def start(self, config, built_files):
        pass

    def stop(self):
        pass

    def get_meta(self):
        return {}

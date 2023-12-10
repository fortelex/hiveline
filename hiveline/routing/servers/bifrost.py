from hiveline.routing.servers.routing_server import RoutingServer, RoutingServerConfig


class BifrostRoutingServer(RoutingServer):
    def build(self, config: RoutingServerConfig, force_rebuild=False) -> list[str]:
        return []

    def start(self, config: RoutingServerConfig, built_files: list[str]):
        pass

    def stop(self):
        pass

    def get_meta(self):
        return {}
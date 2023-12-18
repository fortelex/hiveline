import datetime
from abc import ABC, abstractmethod


class RoutingServerConfig:
    def __init__(self, graph_id: str, target_date: datetime.date, data_dir: str = "./cache", gtfs_files: list[str] = None, osm_files: list[str] = None):
        """
        :param graph_id: the id of the graph
        :param target_date: the target date for the routing (used for pruning time dependent routing graph)
        :param data_dir: the directory where the graph and other files should be cached
        :param gtfs_files: the GTFS files that should be used for routing
        :param osm_files: the OSM files that should be used for routing
        """
        if data_dir.endswith("/"):
            data_dir = data_dir[:-1]
        if gtfs_files is None:
            gtfs_files = []
        if osm_files is None:
            osm_files = []

        self.graph_id = graph_id
        self.target_date = target_date
        self.data_dir = data_dir
        self.gtfs_files = gtfs_files
        self.osm_files = osm_files


class RoutingServer(ABC):
    @abstractmethod
    def build(self, config: RoutingServerConfig, force_rebuild=False) -> list[str]:
        """
        Build the graph for the routing server. This function returns a list of files that are required for routing.
        :param config: the configuration for the routing server
        :param force_rebuild: if True, the graph will be rebuilt even if it already exists in the cache
        :return: a list of files that are required for routing
        """
        pass

    @abstractmethod
    def start(self, config: RoutingServerConfig, built_files: list[str]):
        """
        Start the routing server. It should return when the server is ready to accept requests.
        :param built_files: the files that were built for the routing server
        :param config: the configuration for the routing server
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the routing server.
        """
        pass

    @abstractmethod
    def get_meta(self):
        """
        Get the metadata of the routing server. Includes the version, name, etc.
        """
        pass

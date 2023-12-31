from hiveline.matching.historical_osmnx import get_graph
from hiveline.mongo.db import get_database

if __name__ == "__main__":
    db = get_database()
    get_graph(db, "eef0781a-dce2-4094-8f70-7c41351dc8c5", "Metropolitan Region Eindhoven, Netherlands", True)

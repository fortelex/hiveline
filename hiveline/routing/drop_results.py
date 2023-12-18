from hiveline.mongo.db import get_database


def drop_results(sim_id):
    db = get_database()
    db["route-options"].delete_many({"sim-id": sim_id})
    db["route-results"].delete_many({"sim-id": sim_id})
    db["route-calculation-jobs"].delete_many({"sim-id": sim_id})


if __name__ == "__main__":
    drop_results("7ec1a0c7-b738-41a2-bd59-59614f12efbb")

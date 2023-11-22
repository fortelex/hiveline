from vc import vc_extract

from mongo import mongo


def update_travellers(db, sim_id):
    """
    Update the travellers in the route-options collection
    :param db: the database
    :param sim_id: the simulation id
    :return:
    """
    route_options = db["route-options"]
    virtual_commuters = db["virtual-commuters"]

    for vc in virtual_commuters.find({"sim-id": sim_id}):
        traveller = vc_extract.extract_traveller(vc)

        vc_id = vc["vc-id"]
        route_options.update_one({"sim-id": sim_id, "vc-id": vc_id}, {"$set": {"traveller": traveller}})


if __name__ == "__main__":
    database = mongo.get_database()

    update_travellers(database, "6fed9eee-99e7-45e3-83a2-e31fa2fca449")

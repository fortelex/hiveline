import datetime
import uuid

import pymongo.errors

from hiveline.mongo.db import get_database


def __copy_virtual_commuters(db, from_sim_id, to_sim_id):
    vc = db["virtual-commuters"]

    for doc in vc.find({"sim-id": from_sim_id}):
        doc["sim-id"] = to_sim_id
        del doc["_id"]
        doc["created"] = datetime.datetime.now()
        doc["created-by"] = "virtual commuter duplicator"
        doc["created-from-vc-id"] = doc["vc-id"]

        try:
            vc.insert_one(doc)
        except pymongo.errors.DuplicateKeyError:
            vc.update_one({"sim-id": to_sim_id, "vc-id": doc["vc-id"]}, {"$set": doc})


def duplicate_simulation(db, sim_id, new_sim_id=None, new_date=None, copy_vc=True):
    sims = db["simulations"]

    sim = sims.find_one({"sim-id": sim_id})

    if sim is None:
        raise ValueError("Simulation with id {} not found".format(sim_id))

    if new_sim_id is None:
        new_sim_id = str(uuid.uuid4())

    del sim["_id"]
    sim["created"] = datetime.datetime.now()
    sim["created-by"] = "virtual commuter duplicator"
    sim["created-from-sim-id"] = sim["sim-id"]
    sim["sim-id"] = new_sim_id
    if new_date is not None:
        sim["pivot-date"] = new_date

    sims.insert_one(sim)

    if copy_vc:
        __copy_virtual_commuters(db, sim_id, new_sim_id)

    return new_sim_id


if __name__ == "__main__":
    database = get_database()

    date = datetime.datetime(2022, 10, 4, 8, 0, 0, 0, tzinfo=datetime.timezone.utc)
    sid = duplicate_simulation(database, "8b87b845-5d82-410c-a34d-cf5e4ceba361", new_date=date, copy_vc=True)
    print(sid)  # bd6809da-8113-469f-91cc-501549e8df68

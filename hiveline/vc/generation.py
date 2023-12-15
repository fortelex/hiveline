import uuid
from datetime import datetime, timezone

from hiveline.od.place import Place
from hiveline.mongo.db import get_database, get_place_id
from hiveline.vc.vcgenerator import VirtualCommuterGenerator


def create_simulation(place, pivot_date, num_virtual_commuters=2000, sim_id=None, db=None, use_parking=False,
                      drop_existing=False):
    """
    Generate a bunch of virtual commuters within a simulation and export then to the database
    :param place: the place
    :param pivot_date: the pivot date to use for the simulation (for selection of datasets)
    :param num_virtual_commuters: the number of virtual commuters to generate
    :param use_parking: whether to use parking adjustments to vehicle usage
    :param sim_id: the simulation id (if None, a new one will be generated)
    :param db: the database to use (if None, the default database will be used)
    :param drop_existing: whether to drop existing virtual commuters for this simulation (only if sim_id is set)
    :return:
    """
    if db is None:
        db = get_database()
    if drop_existing and sim_id is not None:
        db["virtual-commuters"].delete_many({"sim-id": sim_id})
        db["simulations"].delete_many({"sim-id": sim_id})
    if sim_id is None:
        sim_id = str(uuid.uuid4())

    place_id = get_place_id(db, place.name)

    # Export simulation to mongo db
    db["simulations"].insert_one({
        "sim-id": sim_id,
        "place-id": place_id,
        "pivot-date": pivot_date,
        "created": datetime.now(),
    })
    print('Simulation inserted to mongo')

    # Virtual commuter generator
    #self.year = pivot_date.year #TODO
    vc_gen = VirtualCommuterGenerator(place)

    print(f'Generating {num_virtual_commuters} virtual commuters')

    # Generate and export virtual commuters
    for i in range(num_virtual_commuters):
        virtual_commuter = vc_gen.generate_commuter(sim_id, use_parking=use_parking)
        virtual_commuter.export_to_mongo(db)

    return sim_id


if __name__ == "__main__":
    # Mongo database
    database = get_database()

    # Simulation parameters
    place_names = [
        'Paris, France']  # ['Dublin Region, Ireland'] #['Leuven, Belgium', 'Dublin, Ireland', 'Vienna, Austria', 'Berlin, Germany'] #"Paris, France"
    for place_name in place_names:
        sim_id = create_simulation(place_name, datetime(2021, 6, 6, 8, 0, 0, 0, tzinfo=timezone.utc), db=database,
                                   use_parking=False)  # Do not use parking adjustments
        print("Done")
        print("place_name: " + place_name)
        print("sim-id: " + sim_id)

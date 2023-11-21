import uuid
from datetime import datetime, timezone
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PROJECT_PATH"))
from mongo.mongo import get_database, get_place_id
from vc.vcgenerator import VirtualCommuterGenerator
from origin_destination.od.place import Place
'''
Generate a bunch of virtual commuters within a simulation
'''

# Mongo database
db = get_database()

# Simulation parameters
place_names = ['Paris, France']#['Dublin Region, Ireland'] #['Leuven, Belgium', 'Dublin, Ireland', 'Vienna, Austria', 'Berlin, Germany'] #"Paris, France"
for place_name in place_names:
    place_id = get_place_id(db, place_name)
    pivot_date = datetime(2021, 6, 6, 8, 0, 0, 0, tzinfo=timezone.utc)
    sim_id = str(uuid.uuid4())
    num_virtual_commuters = 2000

    #Export simulation to mongo db
    db["simulations"].insert_one({
        "sim-id": sim_id,
        "place-id": place_id,
        "pivot-date": pivot_date,
        "created": datetime.now(),
    })
    print('Simulation inserted to mongo')

    # Virtual commuter generator
    city = Place(place_name)
    vc_gen = VirtualCommuterGenerator(city)

    # Generate and export virtual commuters
    for i in range(num_virtual_commuters):
        virtual_commuter = vc_gen.generate_commuter(sim_id, use_parking=False) #Do not use parking adjustments
        virtual_commuter.export_to_mongo(db)

    print("Done")
    print("place_name: "+place_name)
    print("sim-id: " + sim_id)

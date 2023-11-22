import random
import uuid
from datetime import datetime, timezone
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PROJECT_PATH"))
from mongo.mongo import get_database

### Deprecated, use for test only ###

place_name = "Paris, France"
place_id = "d4a5d05a-741f-4d82-9512-87c0413d09ac"
pivot_date = datetime(2018, 6, 6, 8, 0, 0, 0, tzinfo=timezone.utc)

num_virtual_commuters = 1000

min_lat = 48.9325494
min_lon = 2.1592663
max_lat = 48.7901796
max_lon = 2.5303342

lat_diff = max_lat - min_lat
lon_diff = max_lon - min_lon

car_prob = 0.5783358291129846


def random_lat():
    return min_lat + (lat_diff * random.random())


def random_lon():
    return min_lon + (lon_diff * random.random())


points = [[random_lat(), random_lon()] for i in range(num_virtual_commuters * 2)]

db = get_database()

sim_id = str(uuid.uuid4())

db["simulations"].insert_one({
    "sim-id": sim_id,
    "place-id": place_id,
    "pivot-date": pivot_date,
    "created": datetime.now(),
})

commuters = db["virtual-commuters"]

for i in range(num_virtual_commuters):
    origin = points[i * 2]
    destination = points[i * 2 + 1]

    has_car = random.random() < car_prob

    vc = {
        "sim-id": sim_id,
        "place-id": place_id,
        "vc-id": str(uuid.uuid4()),
        "origin": {
            "type": "Point",
            "coordinates": [origin[1], origin[0]]
        },
        "destination": {
            "type": "Point",
            "coordinates": [destination[1], destination[0]]
        },
        "traveller": {
            "employment-location-type": "office",
            "would-use-car": has_car,
            "pc-total-commuters-represented": 1 / num_virtual_commuters
        },
        "created": datetime.now(),
        "departure": pivot_date,
    }

    commuters.insert_one(vc)


print("done")
print("sim-id: " + sim_id)

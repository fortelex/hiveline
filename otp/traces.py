from datetime import datetime

import polyline
import skmob

from mongo.mongo import get_database

vc_set_id = "9a0194be-b1be-425c-a408-98163e03ab56"

db = get_database()
route_results = db["route-results"]

results = route_results.find({"sim-id": vc_set_id})

print("got results")


def get_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000)


map_f = None


for result in results:
    print("got a result")
    # choose first option and its first itinerary

    for option in result["options"]:
        for itinerary in option["itineraries"]:
            line = []

            for leg in itinerary["legs"]:
                points = polyline.decode(leg["legGeometry"]["points"])
                start_date = leg["startTime"]  # unix timestamp in ms
                if "rtStartTime" in leg:
                    start_date = leg["rtStartTime"]
                end_date = leg["endTime"]
                if "rtEndTime" in leg:
                    end_date = leg["rtEndTime"]

                diff = end_date - start_date
                num_points = len(points)

                trajectory = [[point[0], point[1], get_time(start_date + (diff * i / num_points))] for i, point in
                              enumerate(points)]

                line.extend(trajectory)

            tdf = skmob.TrajDataFrame(line, latitude=0, longitude=1, datetime=2)

            map_f = tdf.plot_trajectory(map_f=map_f, max_points=1000, start_end_markers=False)

    break

map_f.save("test.html")

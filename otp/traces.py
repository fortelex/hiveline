from datetime import datetime

import polyline
import skmob

from mongo.mongo import get_database

sim_id = "df2aa812-d0c2-4fb8-aa4c-d0ed6fd0c900"

db = get_database()
route_results = db["route-results"]

results = route_results.find({"sim-id": sim_id})

print("got results")


def get_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000)


map_f = None


for result in results:
    for option in result["options"]:
        if option is None:
            continue

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

            map_f = tdf.plot_trajectory(map_f=map_f, max_points=None, start_end_markers=False, max_users=1000)

map_f.save("test.html")

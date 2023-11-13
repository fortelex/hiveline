from matplotlib import pyplot as plt

import otp


def get_delay_along_route():
    itinerary = otp.get_delayed_route(54.3234385, 10.1225511, 54.7907318, 9.4397184, "2023-11-20", "11:00",
                      ["WALK", "TRANSIT"])
    if itinerary is None:
        return None
    delay = (itinerary["rtEndTime"] - itinerary["endTime"]) / 1000 / 60
    return delay


delays = [get_delay_along_route() for _ in range(30)]

# plot histogram
plt.hist(delays, bins=20)
plt.show()

# OTP Interface

Interface for OpenTripPlanner (OTP) to be used with the [OpenTripPlanner](http://www.opentripplanner.org/) project. For automatic building
of the graph and starting the server, see [here](../readme.md).

## Installation

### Requirements

Download OTP shaded java executable: [otp shaded](https://repo1.maven.org/maven2/org/opentripplanner/otp/2.4.0/) (174mb)

Download OSM pbf file: osm (137mb): [e.g. schlieswig holstein](https://download.geofabrik.de/europe/germany/schleswig-holstein.html)

Download GTFS file: [e.g. schlieswig holstein](https://opendata.schleswig-holstein.de/dataset/fahrplandaten)

Rename GTFS file to something ending with `.gtfs.zip`

Install python requirements:

```bash
pip install -r requirements.txt
```

### Build Graph

```
java -Xmx4G -jar otp-2.4.0-shaded.jar --build --save .
```

### Start Server

```
java -Xmx4G -jar otp-2.4.0-shaded.jar --load .
```

### Explore API at

```
http://localhost:8080/graphiql
```

## Usage

```python
from routing import otp

otp.get_route(54.3234385, 10.1225511, 54.7907318, 9.4397184, "2023-11-20", "11:00",
                      ["WALK", "TRANSIT"])
```

## Setting up delay data

### Download delay data

You can simulate delays using delay histograms. You can find delay statistics on the [Traines Website](https://stats.traines.eu/d/op1pWNF4z/main?orgId=1).

- Select operator in the drop-down menu
- Go to the panel: "Absolute delay histogram of is_departure for operator \<your operator>"
- Select Inspect - Data
- Click on download data

We plan to automate this process in the future.

### Pushing to database

You can push the data to the database using the `otp_reader.py` script. See [here](../mongo/readme.md) to set up the database.

- Put the csv file in the `routing/delay_statistics` folder. Rename it to either the operator name that is used in the GTFS file
  or the [special key](#special-key-average) "average.csv".
- Run `python routing/otp_reader.py`

Now the data is in the database (collection `delay_statistics`) and ready to use in the OTP interface.

### Special key "average"

By default, the delay engine will use a delay based on the histogram of the operator. However, some operators
may not be registered in the delay database. In this case, it will fall back to the "average" key. This is
the histogram of all operators combined. 

Download it in the same way as the operator histograms, but from the panel "Absolute delay histogram of is_departure for product_type regional".

And name it "average.csv" before running `otp_reader.py`.

### Usage

```python
from routing import otp

otp.get_delayed_route(54.3234385, 10.1225511, 54.7907318, 9.4397184, "2023-11-20", "11:00",
                      ["WALK", "TRANSIT"])
```

Note that `get_delayed_route` uses `get_route` internally. If a train cannot be caught due to delays or
cancellations, it will be recalculated.
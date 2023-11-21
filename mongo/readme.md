# MongoDB Interface

Interface for MongoDB to be used with the [MongoDB](https://www.mongodb.com/) project. You can either use a local,
self-hosted, or MongoDB instance or a MongoDB Atlas instance. To use this interface, set up these environment variables:

```bash
UP_MONGO_USER=<username>
UP_MONGO_PASSWORD=<password>
UP_MONGO_DOMAIN=<domain>
UP_MONGO_DATABASE=<database>
PROJECT_PATH=<path to the project folder>
```

Install python requirements:

```bash
pip install -r requirements.txt
```

## Usage

```python
import mongo.mongo

db = mongo.get_database()
```

# Database design
Here are the mongodb collections and their architectures. 

## virtual-commuters

Virtual commuters represents a set of commuters that travel from a given origin to a given destination at a given time.

indexes: _id (unique), vc-id (unique), vc-set-id, created

```json
{
  "_id": ObjectId("655a43323a37aea035f108b9") // mongodb objectID,
  "vc-id": "4b76f10f-aabc-4576-bc49-fcea48065486", // string, uuid
  "sim-id": "6fed9eee-99e7-45e3-83a2-e31fa2fca449", // string, uuid
  "created": "19-11-2023 18:17:38", // datetime
  "origin": {
    // geo coordinates ESPG:4326
    "lon": 2.3633731827663356,
    "lat": 48.86602395912789,
    "tile":  "613047304022130687" // numberLong, H3 tile id
  },
  "destination": {
    // geo coordinates ESPG:4326
    "lon": 2.3159449282175015,
    "lat": 48.89292877524608,
    "tile": "613047308159811583" // numberLong, H3 tile id
  },
  "region": "FR101", // string, NUTS-3 identifier
  "age": "between_20_64", // string
  "employed": true, // boolean
  "employment_type": "office", // string
  "vehicles": {
    "car": 1, // integer or null
    "moto": null, // integer or null
    "utilities": null, // integer or null
    "usage": null // string 
  }
}
```

## regions
Regions are reffering to NUTS-3 regions (Europe), and their associated demographic statistics.  

indexes: _id (unique)
```json
{
  "_id": "AT127", // NUTS-3 id
  "income": 26350, // float
  "age": {
    "under_20": 0.19661529561030935, // float, percentage
    "between_20_64": 0.6002795288106565, // float, percentage
    "over_64": 0.20310517557903418 // float, percentage
  },
  "vehicle": {
    "bus": 0.0007751201070543, // float, probability
    "car": 0.8144969397380679, // float, probability
    "moto": 0.0893559921902993, // float, probability
    "special": 0.1206225823199491, // float, probability
    "utilities": 0.2054163345593881, // float, probability
    "truck": 0.0847937522394389 // float, probability
  },
  "employment_rate": {
    "between_20_64": 78.5, // float, percentage in %
    "over_64": 4.2 // float, percentage in %
  },
  "employment_type": {
    "agricultural": 0.0625552125703634, // float, percentage
    "industrial": 0.9208127290357493, // float, percentage
    "commercial": 0.0073470753593183, // float, percentage
    "office": 0.0032296929962549, // float, percentage
    "social": 0.0060552900383135 // float, percentage
  }
}
```

## places

Places is a set of places (city, metropolitan area, district, etc.) with their geojson shapes and other attributes.

indexes: _id (unique), place-id (unique), place-name

```json
{
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "place-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "place-name": "Hamburg", // string
    "place-country": "DE", // string, locale
    "nuts-3": "DE600", // string, NUTS-3 code
    "bbox": [9.4397184, 54.7907318, 10.1225511, 54.3234385], // geojson bbox
    "shape": { // geojson polygon or multipolygon
        "type": "Polygon",
        "coordinates": [
            [
                [9.4397184, 54.7907318],
                [10.1225511, 54.7907318],
                [10.1225511, 54.3234385],
                [9.4397184, 54.3234385],
                [9.4397184, 54.7907318]
            ]
        ]
    },
    "tiles": [1234, 5678, 9012], // list of long integers, ids of hexagonal tiles (H3) constituting the place
}
```

## tiles

tiles is a set of hexagonal tiles (H3) with their geojson shapes, demographics and other attributes.

indexes: _id (unique), nuts-3

```json
{
  "_id": ObjectId("613047304089239551"), // mongodb objectID
  "nuts-3": "FR101", // NUTS-3 id
  "shape": "POLYGON ((2.349313 48.888085, 2.342995 48.88694, 2.341668 48.882436, 2.346659 48.879077, 2.352976 48.880222, 2.354303 48.884726, 2.349313 48.888085))", // shapely polygon or multipolygon
  "population": 25519, // integer
  "education": 34738.72, // float, area
  "leisure": 75610.60, // float, area
  "empty": 9666.29, // float, area
  "work": {
    "agricultural": 0, // float, area
    "industrial": 3031.73, // float, area
    "commercial": 47823.96, // float, area
    "office": 2400.54, // float, area
    "social": 71336.89, // float, area
    "total": 124592.59 // float, area
  },
  "parking": {
    "destination_car": 0.7708, // float, probability
    "destination_moto": 0.8489, // float, probability
    "origin_car": 0.7708, // float, probability
    "origin_moto": 0.8489 // float, probability
  }
}
```

## place-resources

Place-resources is a set of resources (OSM, GTFS, etc.) for a given place.

indexes: _id (unique), place-id (unique)

```json
{
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "place-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "osm": [ // links of OSM ressources
        {
            "link": "https://download.geofabrik.de/europe/germany/schleswig-holstein-140101.osm.pbf", // link to ressource
            "date": "2014-01-02T01:39:00.000+00:00" // datetime
        }
    ],
    "gtfs": [
        {
            "link": "https://opendata.schleswig-holstein.de/dataset/5e0652d8-7f59-42fc-92ab-a6358f800e1d/resource/edcfffbc-f36b-49d1-befd-0642099f77b9/download/fahrplandaten.zip",
            "date": "2023-12-11T00:00:00.000+00:00"
        }
    ]
}
```

## route-calculation-jobs

Route calculation jobs is a set of jobs to be executed by the route calculation engine.

indexes: _id (unique), vc-id (unique), vc-set-id, state, started

```json
{
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "vc-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "vc-set-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "created": "2023-11-14T13:45:58Z", // datetime
    "state": "pending", // string (pending, running, done, error)
    "error": "error message", // string
    "started": "2023-11-14T14:45:58Z", // datetime
    "finished": "2023-11-14T14:45:59Z", // datetime
}
```

## route-results

Route results is a set of route options for a given virtual commuter.

indexes: _id (unique), vc-id (unique), vc-set-id, created

```json
{
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "vc-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "vc-set-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "created": "2023-11-14T13:45:58Z", // datetime
    "options": [
        {
            "route-option-id": 5678, // integer
            "origin": {
                "type": "Point",
                "coordinates": [10.1225511, 54.3234385]
            }, // geojson point
            "destination": {
                "type": "Point",
                "coordinates": [9.4397184, 54.7907318]
            }, // geojson point
            "departure": "2023-11-20T11:00:00Z", // datetime
            "modes": ["WALK", "TRANSIT"],
            "itinieries": [{...}] // list of itinieries from OTP (OTP format)
        },
        {...}
    ],
    "meta": { // routing meta
        "otp-version": "1.4.0", // string
        "osm-dataset-link": "https://download.geofabrik.de/europe/germany/niedersachsen-latest.osm.pbf", // string
        "osm-dataset-date": "2020-11-14T13:45:58Z", // datetime
        "gtfs-dataset-link": "https://transitfeeds.com/p/vbn/49/latest/download", // string
        "gtfs-dataset-date": "2020-11-14T13:45:58Z", // datetime
        "uses-delay-simulation": true // boolean
    }
}
```

## route-options

Route options is a set of route options for a given virtual commuter.

indexes: _id (unique), vc-id (unique), vc-set-id, created

```json
{
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "vc-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "vc-set-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "created": "2023-11-14T13:45:58Z", // datetime
    "traveller": {
        "employment-location-type": "office", // string (office, industrial, shops, other)
        "would-use-car": true, // boolean (has car and would use it)
        "pc-total-commuters-represented": 0.1, // float, percentage (1 = 100%)
    },
    "options": [
        {
            "route-option-id": 5678, // integer
            "route-duration": 1234, // integer, seconds
            "route-changes": 2, // integer
            "route-delay": 0, // integer, seconds
            "route-recalculations": 0, // integer
            "transport-modes": [ // list of mode description for each leg
                {
                    "type": "walk", // string (walk, cycle, transit, car, motorcycle)
                    "mode-duration": 1234, // integer, seconds
                    "mode-distance": 1234, // integer, meters
                }
            ]
        }
    ]
}
```

## delay-statistics

Delay-statistics is a set of delay statistics for a given public transport operator.

indexes: _id (unique), name (unique)

```json
{
  "_id": ObjectId("654fca427c29f0c249d0babc"), // mongodb objectID
  "name": "abellio rail mitteldeutschland gmbh", // normallized name of the operator
  "starts": [...], // list of delay interval-starts (integer) in minutes
  "weights": [...], // list of delay interval-weights (float) in percentage (1 = 100%)
  "substituted_percent": 0.115, // float, percentage (1 = 100%)
  "cancelled_percent": 4.03 // float, percentage (1 = 100%)
}
```

## simulations
Regrouping the metadata of a simulation  

indexes: _id (unique), sim-id (unique), place-id (unique)
 ```json
 {
  "_id": ObjectId("655a8b20370bc6a1c8b46c2a"), // mongodb objectID
  "sim-id": "6b43b2a5-a45e-438c-8b66-a553b9ad1a46", //string, uuid
  "place-id": ObjectId("655a1771868acf560d1406b6"), // mongodb objectID
  "pivot-date": "2021-06-06T08:00:00.000Z", // datetime, travel time
  "created": "2023-11-19T23:24:32.593Z" // datetime, creation time
}
 ```

 ## stats
 Statistics gathered for a simulation  

 indexes: _id (unique), sim-id (unique), stat-id (unique)

 ```json
 {
  "_id": ObjectId("655b55841cafc71d549ea498"), // mongodb objectID
  "sim-id": "20dc997d-5e66-4d7c-a8f7-b50ca9ef0096", //string, uuid
  "stat-id": "459e4ee0-5f1e-4e9f-8f3a-d668386a4b33", //string, uuid
  "created": "2023-11-20T13:48:04.654Z", // datetime
  "base-stats": {
    "total_car_meters": 1960442.622613225, // float
    "total_transit_meters": 1400452.2989545446, // float
    "total_walk_meters": 3063270.3960457495, // float
    "total_car_passengers": 361, // integer
    "total_transit_passengers": 163, // integer
    "total_walkers": 794, // integer
    "car_owners_choosing_cars": 361, // integer
    "car_owners_choosing_transit": 4, // integer
    "car_owners_choosing_walk": 16, // integer
    "would_use_car_count": 381, // integer
    "wouldnt_use_car_count": 938 // integer
  },
  "upper-transit-modal-share": 0.24388387518357973, // float
  "modal-shares": {
    "car_share": 0.2101162163775182, // float
    "transit_share": 0.06777260186258077, // float
    "walk_share": 0.7221111817599011 // float
  },
  "meta": {
    "name": "Paris 2019", // string
    "inhabitants": 2000000, // integer
    "car_owner_override": 0, // integer
    "method": "no-congestion" // string
  }
}
 ```
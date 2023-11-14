# Database design

## virtual-commuters

Virtual commuters represents a set of commuters that travel from a given origin to a given destination at a given time.

indexes: _id (unique), vc-id (unique), vc-set-id, place-id, created

```js
doc = {
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "vc-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "vc-set-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid (in case we have multiple sets of virtual commuters for each place)
    "created": "2023-11-14T13:45:58Z", // datetime
    "place-id": "f1f60eac-d3bf-4c01-9426-b8a2b6854717", // string, uuid
    "origin": {
        "type": "Point",
        "coordinates": [10.1225511, 54.3234385]
    }, // geojson point
    "destination": {
        "type": "Point",
        "coordinates": [9.4397184, 54.7907318]
    }, // geojson point
    "departure": "2023-11-20T11:00:00Z", // datetime
    "traveller": {
        "employment-location-type": "office", // string (office, industrial, shops, other)
        "would-use-car": true, // boolean (has car and would use it)
        "pc-total-commuters-represented": 0.1, // float, percentage (1 = 100%)
    }
}
```

## route-calculation-jobs

Route calculation jobs is a set of jobs to be executed by the route calculation engine.

indexes: _id (unique), vc-id (unique), vc-set-id, state, started

```js
doc = {
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

```js
doc = {
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

```js
doc = {
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

## places

Places is a set of places (cities, towns, villages, etc.) with their geojson shapes and other attributes.

indexes: _id (unique), place-id (unique), place-name

```js
doc = {
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
    "tiles": [1234, 5678, 9012], // list of long integers (or strings), Ids of hexagonal tiles (H3) constituting the city
}
```

## hex-tiles

Hex-tiles is a set of hexagonal tiles (H3) with their geojson shapes, demographics and other attributes.

indexes: _id (unique), tile-id (unique)

```js
doc = {
    "_id": ObjectId("5f9f5f1d9b0b1d0b1d0b1d0b"), // mongodb objectID
    "tile-id": 1234, // long integer (or string), Id of hexagonal tile (H3)
    "shape": { // geojson polygon
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
    "population-density": 0.1, // float, percentage (1 = 100%)
    "zoning": { // zoning percentages, sum of all percentages = 1
        "habitation": 0.1, // float, percentage (1 = 100%)
        "office": 0.2, // float, percentage (1 = 100%)
        "industrial": 0.1, // float, percentage (1 = 100%)
        "shops": 0.6, // float, percentage (1 = 100%)
    },
    "demographics": {
        "free-parking": 0.1, // float
    }
}
```

## place-resources

Place-resources is a set of resources (OSM, GTFS, etc.) for a given place.

indexes: _id (unique), place-id (unique)

```js
doc = {
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

## delay-statistics

Delay-statistics is a set of delay statistics for a given public transport operator.

indexes: _id (unique), name (unique)

```js
doc = {
  "_id": ObjectId("654fca427c29f0c249d0babc"), // mongodb objectID
  "name": "abellio rail mitteldeutschland gmbh", // normallized name of the operator
  "starts": [...], // list of delay interval-starts (integer) in minutes
  "weights": [...], // list of delay interval-weights (float) in percentage (1 = 100%)
  "substituted_percent": 0.115, // float, percentage (1 = 100%)
  "cancelled_percent": 4.03 // float, percentage (1 = 100%)
}
```

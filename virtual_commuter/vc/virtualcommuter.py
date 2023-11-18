from datetime import datetime
import uuid


class VirtualCommuter():
    def __init__(self, sim_id, origin_tile, origin, destination_tile, destination, region, age, employed, employment_type, vehicles):
        '''
        Create a virtual commuter
        '''
        self.origin_tile = int(origin_tile)
        self.origin = origin
        # the destination can be None
        self.destination_tile = int(destination_tile) if destination_tile else None
        self.destination = destination
        self.region = region
        self.age = age
        self.employed = bool(employed)
        self.employment_type = employment_type
        self.vehicles = vehicles
        self.sim_id = sim_id
        self.id = str(uuid.uuid4())
        self.created = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    def export_to_mongo(self, db):
        '''
        Push the virtual commuter to mongo database
        Args:
            db (mongo db): The database object to connect
        '''
        data = {
            'vc-id': self.id,
            'sim-id': self.sim_id,
            'created': self.created,
            'origin': {
                'lon': self.origin.x,
                'lat': self.origin.y,
                'tile': self.origin_tile
            },
            'destination':  {
                'lon': self.destination.x if self.destination else None,
                'lat': self.destination.y if self.destination else None,
                'tile': self.destination_tile
            },
            'region': self.region,
            'age': self.age,
            'employed': self.employed,
            'employment_type': self.employment_type,
            'vehicles': self.vehicles,
        }
        db['virtual-commuters'].insert_one(data)
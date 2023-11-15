# landuse classification
landuse_dict = {
    'work': ['commercial', 'construction', 'industrial', 'retail', 'institutional', 'aquaculture', 'farmyard', 'port', 'quarry'],
    'leisure': ['fairground', 'retail', 'recreation_ground', 'religious', 'winter_sports'],
    'empty': ['allotments', 'farmland', 'paddy', 'animal_keeping', 'flowerbed', 'forest', 'grass', 'greenhouse_horticulture', 'meadow', 'orchard', 'plant_nursery', 'vineyard', 'village_green', 'greenfield', 'brownfield', 'landfill', 'cemetery', 'garages', 'military', 'railway']
}
# by empty, understand not much traffic flow

work_tags = {
    'landuse': landuse_dict['work'],
    'office': True,
    'shop': True,
    'healthcare': True
}

education_tags = {
    'landuse': 'education',
    'amenity': ['kindergarten', 'school', 'college', 'university']
}

leisure_tags = {
    'landuse': landuse_dict['leisure'],
    'shop': True,
    'leisure': True,
    'sport': True,
    'tourism': True,
}

empty_tags = {
    'landuse': landuse_dict['empty'],
    'natural': 'water'
}

# landuse classification
landuse_dict = {
    'work': ['commercial', 'construction', 'industrial', 'retail', 'institutional', 'aquaculture', 'farmyard', 'port', 'quarry'],
    'leisure': ['fairground', 'retail', 'recreation_ground', 'religious', 'winter_sports'],
    'empty': ['allotments', 'farmland', 'paddy', 'animal_keeping', 'flowerbed', 'forest', 'grass', 'greenhouse_horticulture', 'meadow', 'orchard', 'plant_nursery', 'vineyard', 'village_green', 'greenfield', 'brownfield', 'landfill', 'cemetery', 'garages', 'military', 'railway']
}

work_agricultural_tags = {
    'landuse': ['aquaculture', 'farmyard'],
}
work_industrial_tags = {
    'landuse': ['industrial', 'construction', 'port', 'quarry'],
}
work_commercial_tags = {
    'landuse': ['retail', 'commercial'],
    'shop': True,
    'amenity': ['restaurant', 'fast_food'],
}
work_office_tags = {
    'office': True,
}
work_social_tags = {
    'landuse': ['institutional', 'civic_admin', 'education'],
    'amenity': ['kindergarten', 'school', 'college', 'university'],
    'healthcare': True,
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

building_tags = {
    '1':{
        'building': ['apartments', 'house', 'commercial', 'retail', 'farm', 'hotel']
        },
    '2':{
        'building': ['industrial', 'yes'],
        'landuse':'construction',
    }
}

parking_tags ={
    'landuse': ['allotments', 'farmland', 'animal_keeping', 'flowerbed', 'forest', 'grass', 'greenhouse_horticulture', 'meadow', 'orchard', 'plant_nursery', 'vineyard', 'village_green', 'greenfield', 'brownfield', 'landfill', 'cemetery', 'military', 'railway'],
    'natural': ['water','wood','riverbed']
}   
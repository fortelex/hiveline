# Virtual commuters generator
The [`vc`](vc) package can generate virtual commuters according to a given place. 

All the attributes of the virtual commuters (vc) are taken randomly according to the tile and region statistics.  
For example, a random tile then location in it are selected for the current vc. The age of the vc is drawn, and a job or not is attributed according to the age range and the employment rates. Then, the type of work is defined and affects the workplace, that is the destination location. Vehicles can be owned and used.  

The [`generation.py`](generation.py) file is using this to generate a bunch of virtual commuters and export them to the mongo database.
# Data sources
This contains the datasets used for extracting the demographic information. This is then used to generate the origins / destinations of each virtual commuter. All precise sources are listed in `source.txt` files.  

## Demographic data
The data comes from [eurostat](https://ec.europa.eu/eurostat/) that has normalized scales to compute statistics based on european regions and subregions. These are called NUTS, the most precise being NUTS-3. Some data is available only for NUTS-2, we expressed everything at a NUTS-3 level for usability.  
![](../docs/img/eurostat-nuts.jpg)  

More details on each dataset can be found in [data_cleaning.ipynb](./data_cleaning.ipynb), where all the transformations are done.  

Summary of the extracted datasets: 

| Variable | Unit | Resolution | Categories | 
|---|---|---|---|
| Age | Count | NUTS-3 | 3 |
|Employment rate|Percentage | NUTS-2 | 2 |
|Employment type |Percentage | NUTS-3 | 10 |
|Motorization rate|Probability | NUTS-2 | 6 |
|Income|€ per inhabitant | NUTS-2 | |


## Origin: population density
[Kontur](https://www.kontur.io/portfolio/population-dataset/) is proposing an estimation of the worldwide population density, at a precise scale. The hexagonal tiling system [H3](https://h3geo.org/) is used at scale 8, that means that every hexagon has an area of $\approx 0.7 km^2$. This tiling is used in our code to discretize the map and standardize the zoning data.  

## Destination: zoning data
The destinations are computed from [Open Street Map](https://www.openstreetmap.org/) zoning data. Different zones are set according to the travel purpose:

- work
- education
- leisure

And more precisely for employment types: 
- agricultural
- industrial
- commercial
- office
- social

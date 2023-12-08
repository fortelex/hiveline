# Map visualization
The [`plot.map`](plot/map.py) module is useful for more advanced visualisation, integrating an interactive map.

```python
from od.place import Place
from visualization.plot.map import CityPlotter

# declare the place
place_name = 'Dublin Region, Ireland'
city = Place(place_name)

# declare a map
plotter = CityPlotter(city, zoom=11)

# add layers
column = 'population'
plotter.add_hex_heatmap(column)
plotter.add_city_shape()

# plot
plotter.show_map()

# save the image
plotter.export_to_png(filename='dublin_region_'+column, tall_city=True)
```
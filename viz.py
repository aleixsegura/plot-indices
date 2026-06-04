import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.geometry.base import BaseMultipartGeometry

def draw_polygon(geometry: BaseMultipartGeometry, name: str):
    """
    For debugging and frontend utilities.
    """
    
    plt.figure()

    for poly in geometry.geoms:
        if isinstance(poly, Polygon):
            x, y = poly.exterior.xy
            plt.plot(x, y)
            plt.fill(x, y, alpha=0.3)
 
    plt.axis('equal')

    save_path = f'figures/{name}.png'
    plt.savefig(save_path)
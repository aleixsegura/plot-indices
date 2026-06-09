import os
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

    os.makedirs('figures/', exist_ok=True)

    save_path = f'figures/{name}.png'
    plt.savefig(save_path)
    plt.close()


def draw_raster(img, name: str, cmap_: str):
    os.makedirs('figures/rasters', exist_ok=True)
    save_path = f'figures/rasters/{name}.png'

    plt.imshow(img, cmap = cmap_) # vmin - 1, vmax 2
    plt.colorbar()
    plt.title(f'{name}')
    
    plt.savefig(save_path)
    plt.close()
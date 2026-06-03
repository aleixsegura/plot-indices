import os
import requests
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely import wkt
from tokengen import gen_token
from dotenv import load_dotenv
from shapely.geometry import box, Polygon
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

# Catastro (Hacienda): delimita propietat legal (parcel·les). Propietari, valor...
# SIGPAC (Agricultura): ús agrícola real (recintes). Que hi ha plantat.
# SIEX 

config = {
    "odata_base_url": "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
    "s3_endpoint_url": "https://eodata.dataspace.copernicus.eu",
}


DB_PROPERTIES = {
    'Mata': ['25:157:0:0:8:106', '25:157:0:0:8:216', '25:157:0:0:8:219', '25:168:0:0:19:2', '25:168:0:0:19:3', '25:168:0:0:19:4', '25:168:0:0:19:103'],
    'Montolivet': ['25:157:0:0:78', '25:157:0:0:79', '25:157:0:0:7:81', '25:168:0:0:80', '25:168:0:0:20:84'],
    'Vinya': ['25:168:0:0:10:6'],
    'Mitjana': ['25:168:0:0:9:68'],
    'Pedros': ['25:254:0:0:13:98'],
    'Sort Calsones': ['25:254:0:0:22:116']
}

ROUTE_PREFIX = 'http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx?service=WFS&version=2.0.0&request=GetFeature&STOREDQUERY_ID=GetParcel&refcat='

REFCATS = {
    'Mata': ['25157A008001060000XJ', '25157A008002160000XG', '25157A008002190000XL', '25168A019000020000IT', '25168A019000030000IF', '25168A019000040000IM', '25168A019001030000IK'],
    'Montolivet': ['25157A007000780000XB', '25157A007000790000XY', '25157A007000810000XB', '25168A020000800000IQ', '25168A020000840000IF'],
    'Vinya': ['25168A010000060000IZ'],
    'Mitjana': ['25168A009000680000IP'],
    'Pedros': ['25254A013000980000XU'],
    'Sort Calsones': ['25254A022001160000XH']
}


load_dotenv()

USER = os.getenv('username')
PASSWORD = os.getenv('password')


def extract_image(geometry: BaseMultipartGeometry):

    bounds = geometry.bounds
    box_ = box(*bounds)
    wkt_string = box_.wkt

    plt.figure()

    for poly in geometry.geoms:
        if isinstance(poly, Polygon):
            x, y = poly.exterior.xy
            plt.plot(x, y)
            plt.fill(x, y, alpha=0.3)
 
    plt.axis('equal')
    plt.savefig('vinya.png')

    filter = (
        f"Collection/Name eq 'SENTINEL-2' and "
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt_string}') and "
        f"ContentDate/Start gt 2026-02-01T00:00:00.000Z"
    )

    params = {
        '$filter': filter,
        '$top': 1, # 1 most recent results
        '$orderby': 'ContentDate/Start desc'
    }

    try:
        response = requests.get(config['odata_base_url'], params=params, timeout=15)

        if response.status_code != 200:
            print(f'Error calling Copernicus API. Status code = {response.status_code}')
            return None
        
        else:
            data = response.json()
            print(data, end='\n\n')
            
            product_id = data['value'][0]['Id']
            s3_path = data['value'][0]['S3Path']
            
            print(product_id, s3_path)

            # image_url = f'https://catalogue.dataspace.copernicus.eu/odata/v1/Products({image_id})/$value'

            if USER is None or PASSWORD is None:
                raise ValueError('No user or password provided')

            token = gen_token(USER, PASSWORD)
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
                }


    except Exception as e:
        print(f'Connection error: {e}')


try:
    wfs_url_test = f'{ROUTE_PREFIX}{REFCATS['Vinya'][0]}'
    gdf = gpd.read_file(wfs_url_test)

    area_m2 = gdf['areaValue'].item()
    pos = gdf['pos'].item()
    geometry = gdf.geometry.item()
    
    type_ = geometry.geom_type

    if isinstance(geometry, BaseMultipartGeometry):
        extract_image(geometry)

except Exception as e:
    print(f'Error connecting to Catastro API: {e}')
    exit(1)

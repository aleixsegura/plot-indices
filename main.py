import os
import boto3
import pyproj
import requests
import numpy as np
import rasterio
import rasterio.mask
import geopandas as gpd
import matplotlib.pyplot as plt
from tqdm import tqdm
from time import sleep
from typing import Any, Optional
from pathlib import Path
from viz import draw_polygon, draw_raster
from tokengen import gen_token
from dotenv import load_dotenv
from shapely.ops import transform
from shapely.geometry import box
from shapely.geometry.base import BaseMultipartGeometry

# Catastro (Hacienda): delimita propietat legal (parcel·les). Propietari, valor...
# SIGPAC (Agricultura): ús agrícola real (recintes). Que hi ha plantat.
# SIEX: REA (Registre d'Explotacions) + CUE (Cuaderns Digitals Explotacions)


odata_base_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
s3_endpoint_url = "https://eodata.dataspace.copernicus.eu",

BANDS = {
    'blue': 'B02',
    'green': 'B03',
    'red': 'B04',
    'red_edge_1': 'B05',
    'red_edge_2': 'B06',
    'red_edge_3': 'B07',
    'infrared': 'B08',
    'narrow_infrared': 'B8A',
    'swir_1':'B11',
    'swir_2': 'B12'
}


DB = {
    'mata': ['25:157:0:0:8:106', '25:157:0:0:8:216', '25:157:0:0:8:219', '25:168:0:0:19:2', '25:168:0:0:19:3', '25:168:0:0:19:4', '25:168:0:0:19:103'],
    'montolivet': ['25:157:0:0:78', '25:157:0:0:79', '25:157:0:0:7:81', '25:168:0:0:80', '25:168:0:0:20:84'],
    'vinya': ['25:168:0:0:10:6'],
    'mitjana': ['25:168:0:0:9:68'],
    'pedros': ['25:254:0:0:13:98'],
    'sort_calsones': ['25:254:0:0:22:116']
}

ROUTE_PREFIX = 'http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx?service=WFS&version=2.0.0&request=GetFeature&STOREDQUERY_ID=GetParcel&refcat='

REFCATS = {
    'mata': ['25157A008001060000XJ', '25157A008002160000XG', '25157A008002190000XL', '25168A019000020000IT', '25168A019000030000IF', '25168A019000040000IM', '25168A019001030000IK'],
    'montolivet': ['25157A007000780000XB', '25157A007000790000XY', '25157A007000810000XB', '25168A020000800000IQ', '25168A020000840000IF'],
    'vinya': ['25168A010000060000IZ'],
    'mitjana': ['25168A009000680000IP'],
    'pedros': ['25254A013000980000XU'],
    'sort_calsones': ['25254A022001160000XH']
}


load_dotenv()

USER = os.getenv('username')
PASSWORD = os.getenv('password')



def get_temporary_s3_credentials(headers: dict):
    """
    Create temporary S3 credentials by calling the S3 keys manager API.
    """
    credentials_response = requests.post("https://s3-keys-manager.cloudferro.com/api/user/credentials", headers=headers)
    
    if credentials_response.status_code == 200:
        s3_credentials = credentials_response.json()
        print("Temporary S3 credentials created successfully.")
        return s3_credentials
    else:
        print(f"Failed to create temporary S3 credentials. Status code: {credentials_response.status_code}")
        print("Product download aborted.")
        exit(1)


def format_filename(filename, length=40):
    """
    Format a filename to a fixed length, truncating if necessary.
    """
    if len(filename) > length:
        return filename[:length - 3] + '...'
    else:
        return filename.ljust(length)

def download_file_s3(s3, bucket_name, s3_key, local_path, failed_downloads):
    """
    Download a file from S3 with a progress bar.
    Track failed downloads in a list.
    """
    try:
        file_size = s3.head_object(Bucket=bucket_name, Key=s3_key)['ContentLength']
        formatted_filename = format_filename(os.path.basename(local_path))
        with tqdm(total=file_size, unit='B', unit_scale=True, desc=formatted_filename, ncols=80, bar_format='{desc:.40}|{bar:20}| {percentage:3.0f}% {n_fmt}/{total_fmt}B') as pbar:
            def progress_callback(bytes_transferred):
                pbar.update(bytes_transferred)

            s3.download_file(bucket_name, s3_key, local_path, Callback=progress_callback)
    except Exception as e:
        print(f"Failed to download {s3_key}. Error: {e}")
        failed_downloads.append(s3_key)


def traverse_and_download_s3(s3_resource, bucket_name, base_s3_path, local_path, failed_downloads):
    """
    Traverse the S3 bucket and download all files under the specified prefix.
    """
    bucket = s3_resource.Bucket(bucket_name)
    files = bucket.objects.filter(Prefix=base_s3_path)

    for obj in files:
        s3_key = obj.key
        relative_path = os.path.relpath(s3_key, base_s3_path) # Nom sol de l'arxiu + carpetes anidades sense ruta completa dins bucket
        local_path_file = os.path.join(local_path, relative_path)
        local_dir = os.path.dirname(local_path_file) # Nom de la carpeta downloads/eodata/Sentinel2/DATASTRIP sense nom de l'arxiu
        os.makedirs(local_dir, exist_ok=True)
        download_file_s3(s3_resource.meta.client, bucket_name, s3_key, local_path_file, failed_downloads)


def download_product(geometry: BaseMultipartGeometry) -> None:

    bounds = geometry.bounds
    box_ = box(*bounds)
    wkt_string = box_.wkt

    print(wkt_string)
    
    if len(os.listdir('downloads/eodata/Sentinel-2')) > 0:
        return

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
        response = requests.get(odata_base_url, params=params, timeout=15)

        if response.status_code != 200:
            print(f'Error calling Copernicus API. Status code = {response.status_code}')
            return None
        
        else:
            data = response.json()

            product_id = data['value'][0]['Id']
            s3_path = data['value'][0]['S3Path']

            print(f'Product id = {product_id}, S3 path = {s3_path}')

            if USER is None or PASSWORD is None:
                raise ValueError('No user or password provided')
            
            token = gen_token(USER, PASSWORD)
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }

            s3_credentials = get_temporary_s3_credentials(headers)

            sleep(5)

            print(f'S3 credentials = {s3_credentials}, Type = {type(s3_credentials)}')

            s3_resource = boto3.resource('s3',
                                         endpoint_url=s3_endpoint_url,
                                         aws_access_key_id=s3_credentials['access_id'],
                                         aws_secret_access_key=s3_credentials['secret']
                                         )
            
            folder = 'downloads/eodata/Sentinel-2/'
            os.makedirs(folder, exist_ok=True)

            bucket_name, base_s3_path = s3_path.lstrip('/').split('/', 1)
            print(f'Bucket name = {bucket_name}, Base path = {base_s3_path}')
            
            failed_downloads = []
            traverse_and_download_s3(s3_resource, bucket_name, base_s3_path, folder, failed_downloads)
            
            print(failed_downloads)

    except Exception as e:
        print(f'Connection error: {e}')


def get_band_path(band: str, res: str = '10m') -> Path | None:
    prefix = Path('downloads/eodata/Sentinel-2/GRANULE')

    band_path = next(prefix.rglob(f'*{band}_{res}.jp2'), None)

    return band_path


def clip(geometry: BaseMultipartGeometry, band_path: Path):

    project = pyproj.Transformer.from_crs(
        'EPSG:4326',
        'EPSG:32631',
        always_xy=True,
    ).transform

    geom_utm = transform(project, geometry)
    
    with rasterio.open(band_path) as band_image:
        band_out, _ = rasterio.mask.mask(
            band_image,
            [geom_utm],
            crop=True,
            filled=False,
        )

    return band_out.squeeze().astype('float32')


def ndvi(red, infrared):
    out = (infrared - red) / (red + infrared)
    return out


def gndvi(green, infrared):
    out = (infrared - green) / (green + infrared)
    return out


def ndwi(green, swir_1):
    out = (green - swir_1) / (green + swir_1)
    return out


def ndmi(narrow_infrared, swir_1):
    out = (narrow_infrared - swir_1) / (narrow_infrared + swir_1)
    return out


def require(path: Path | None) -> Path:
    if path is None:
        raise ValueError('Missing band path')
    return path


def compute_indices(geometry: BaseMultipartGeometry):
    green_band = require(get_band_path('B03'))
    green_band_20m = require(get_band_path('B03', '20m'))
    red_band = require(get_band_path('B04'))
    infrared_band = require(get_band_path('B08'))
    narrow_infrared_band_20m = require(get_band_path('B8A', '20m'))
    swir_1_band_20m = require(get_band_path('B11', '20m'))

    green = clip(geometry, green_band)
    green_20m = clip(geometry, green_band_20m)
    red = clip(geometry, red_band)
    infrared = clip(geometry, infrared_band)
    narrow_infrared = clip(geometry, narrow_infrared_band_20m)
    swir_1 = clip(geometry, swir_1_band_20m)

    ndvi_ = ndvi(red, infrared)
    gndvi_ = gndvi(green, infrared)
    ndwi_ = ndwi(green_20m, swir_1)
    ndmi_ = ndmi(narrow_infrared, swir_1)

    draw_raster(ndvi_, 'ndvi', 'RdYlGn')
    draw_raster(gndvi_, 'gndvi', 'RdYlGn')
    draw_raster(ndwi_, 'ndwi', 'Blues')
    draw_raster(ndmi_, 'ndmi', 'BrBG')

try:
    wfs_url_test = f'{ROUTE_PREFIX}{REFCATS['vinya'][0]}'
    gdf = gpd.read_file(wfs_url_test)

    area_m2 = gdf['areaValue'].item()
    pos = gdf['pos'].item()
    geometry = gdf.geometry.item()
    
    type_ = geometry.geom_type

    if isinstance(geometry, BaseMultipartGeometry):
        draw_polygon(geometry, 'vinya')
        download_product(geometry)
        compute_indices(geometry)

except Exception as e:
    print(f'Unexpected error: {e}')
    exit(1)

import ee
from typing import Tuple, Callable
import utm
from shapely.geometry import box
import numpy as np
import math
import pandas as pd
from dataclasses import dataclass 
from osgeo import gdal
import pathlib



def warp_neon_dir(dir_path):
    """
    Recibe un objeto pathlib.Path (o algo convertible a Path),
    busca los .tif en ese directorio y los une en un archivo .tif
    de salida con las opciones deseadas.
    """

    dir_path = pathlib.Path(dir_path)
    input_files = list(dir_path.glob("*.tif"))
    output_file = dir_path.with_suffix(".tif")

    if output_file.exists():
        print(f"{output_file} exists")
        return output_file.as_posix()
    else:
        warp_options = gdal.WarpOptions(
            format='GTiff',
            outputType=gdal.GDT_UInt16,
            srcNodata=0,         # Nodata de entrada
            dstNodata=65535,     # Nodata de salida
            creationOptions=[
                "TILED=YES",
                "BLOCKXSIZE=256",
                "BLOCKYSIZE=256",
                "COMPRESS=ZSTD",
                "ZSTD_LEVEL=13",
                "PREDICTOR=2",
                "NUM_THREADS=20",
                "INTERLEAVE=BAND"
            ]
        )

        gdal.Warp(
            destNameOrDestDS=output_file.as_posix(),
            srcDSOrSrcDSTab=[str(f) for f in input_files],
            options=warp_options
        )
        
        return output_file 
    

def warp_single_tif(input_tif, output_tif):

    input_tif = pathlib.Path(input_tif)
    output_tif = pathlib.Path(output_tif)

    output_tif.parent.mkdir(parents=True, exist_ok=True)

    if output_tif.exists():
        print(f"{output_tif} ya existe.")

    else:
        warp_options = gdal.WarpOptions(
            format='GTiff',
            outputType=gdal.GDT_UInt16,
            dstNodata=65535,
            creationOptions=[
                "TILED=YES",
                "BLOCKXSIZE=64",
                "BLOCKYSIZE=64",
                "COMPRESS=ZSTD",
                "ZSTD_LEVEL=13",
                "PREDICTOR=2",
                "NUM_THREADS=20",
                "INTERLEAVE=BAND"
            ]
        )

        gdal.Warp(
            destNameOrDestDS=str(output_tif),
            srcDSOrSrcDSTab=[str(input_tif)],
            options=warp_options
        )

        print(f"{output_tif} generado.")
        



def fetch_and_save_get(ulist, full_outname):
    """Descarga la imagen con computePixels y la guarda en disco."""
    images_bytes = ee.data.getPixels(ulist)
    with open(full_outname, "wb") as src:
        src.write(images_bytes)

def fetch_and_save(ulist, full_outname):
    """Descarga la imagen con computePixels y la guarda en disco."""
    images_bytes = ee.data.computePixels(ulist)
    with open(full_outname, "wb") as src:
        src.write(images_bytes)

def convert_utm_to_geographic(row):
    """
    Converts UTM coordinates to geographic coordinates (latitude, longitude).
    Extracts the zone from the EPSG code.

    Args:
        row (pandas.Series): Row of the DataFrame containing UTM coordinates and EPSG code.

    Returns:
        Tuple[float, float]: Geographic coordinates (latitude, longitude).
    """
    # Extract UTM coordinates (x, y) and the zone from the 'epsg' column
    utm_coord = (row['x_c'], row['y_c'])
    epsg_code = row['epsg']
    
    # Extract the zone from the EPSG code (e.g., "EPSG:32613" → zone = 32613)
    zone = int(epsg_code.split(":")[1])  # Extract the UTM zone number (e.g., 32613 → 32613)
    
    # If the zone is between 32601 and 32660 (northern hemisphere), use 'northern=True';
    # if it is from 32701 to 32760 (southern hemisphere), use 'northern=False'
    northern = True if zone <= 32700 else False
    zone = int(str(zone)[-2:])  # Get only the last two digits of the zone

    # Convert UTM to geographic coordinates (lat, lon)
    lat, lon = utm.to_latlon(utm_coord[0], utm_coord[1], zone, northern=northern)
    
    return lat, lon

def subdivide_row(row, tile_size=5160):
    n_cols = math.ceil(row['distx'] / tile_size)
    n_rows = math.ceil(row['disty'] / tile_size)
    
    tiles = []
    for i in range(n_rows):
        for j in range(n_cols):
            row_copy = row.copy()
            row_copy['x'] = row['x'] + j * tile_size
            row_copy['y'] = row['y'] - i * tile_size
            tiles.append(row_copy)
    return tiles

def calculate_centroid(row):
    coordinates = row['coordinates'][0]  # Accede a las coordenadas
    coords_array = np.array(coordinates)  # Convierte las coordenadas en un array de numpy
    lons = coords_array[:, 0]
    lats = coords_array[:, 1]
    clon = ((lons.max() - lons.min()) / 2) + lons.min()
    clat = ((lats.max() - lats.min()) / 2) + lats.min()
    centroid = (clon, clat)
    return centroid

def calculate_coord(row):
    coordinates = row['coordinates'][0]  # Accede a las coordenadas
    coords_array = np.array(coordinates)  # Convierte las coordenadas en un array de numpy
    lons = coords_array[:, 0]
    lats = coords_array[:, 1]
    clon = lons.min()
    clat = lats.max()
    coord = (clon, clat)
    return coord

def geo2utm_from_tuple(centroid) -> tuple[float, float, str]:
    return geo2utm(centroid[0], centroid[1])

def geo2utm(lon: float, lat: float) -> tuple[float, float, str]:
    """
    Converts latitude and longitude coordinates to UTM coordinates and returns the EPSG code.

    Args:
        lon (float): Longitude.
        lat (float): Latitude.

    Returns:
        Tuple[float, float, str]: UTM coordinates (x, y) and the EPSG code.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    epsg_code = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return x, y, f"EPSG:{epsg_code}"

def image_to_feature(img: ee.Image) -> ee.Feature:
    """
    Converts an Earth Engine image to a feature, including its footprint and associated metadata.

    Args:
        img (ee.Image): An Earth Engine image object.

    Returns:
        ee.Feature: A feature containing the footprint and metadata of the image.
    """
    ring = ee.Geometry(img.get("system:footprint"))
    poly = ee.Geometry.Polygon([ring.coordinates()])
    ft = ee.Feature(poly, img.toDictionary())
    ft = ft.set({
        "id_geom_array": ee.List([
            img.get("system:id"),
            img.get("system:time_start"),
            poly
        ])
    })
    return ft


def get_utm_epsg(lat: float, lon: float) -> int:
    """
    Converts latitude and longitude coordinates to UTM (Universal Transverse Mercator) coordinates 
    and returns the corresponding EPSG code.

    Args:
        lat (float): Latitude in decimal degrees.
        lon (float): Longitude in decimal degrees.

    Returns:
        int: EPSG code of the UTM projection corresponding to the provided coordinates.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    epsg_code = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return int(epsg_code)

def square_around_point(point_utm: ee.Geometry, side: float = 2565) -> box:
    """
    Generates a square polygon around a given point in UTM coordinates.

    Args:
        point_utm (ee.Geometry): Point geometry in UTM coordinates.
        side (float, optional): The length of the side of the square (in meters). Defaults to 2565.

    Returns:
        box: A square geometry centered around the input point.
    """
    x_cen, y_cen = point_utm.x, point_utm.y
    half_side = side / 2.0
    return box(x_cen - half_side, y_cen - half_side,
                    x_cen + half_side, y_cen + half_side)

def create_image_with_null_property(row: dict) -> ee.Image:
    """
    Creates an image and computes the percentage of null (missing) values in a specified region.

    Args:
        row (dict): A dictionary containing the following keys:
            - "lat": Latitude of the center point of the region.
            - "lon": Longitude of the center point of the region.
            - "utm": The EPSG code for the UTM projection.
            - "neon_id": The ID of the base image for the region.

    Returns:
        ee.Image: The base image with an additional property "nullPercent" indicating the percentage 
                  of missing data within the region.
    """
    point = ee.Geometry.Point(
        [float(row["lon_c"]), 
         float(row["lat_c"])]
    )
    square_5120m = (point
        .transform(row["epsg"], 1)
        .buffer(2580)
        .bounds()
        .transform("EPSG:4326", 1)
    )

    base_img = ee.Image(row["neon_id_gee"])
    two_band = ee.Image.constant(1) \
                 .rename("constant") \
                 .addBands(base_img.select("B001"))
    
    count_dict = two_band.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=square_5120m,
        scale=100,
        bestEffort=True
    )
    total_pixels = ee.Number(
        count_dict.get("constant")
    )
    valid_pixels = ee.Number(
        count_dict.get("B001")
    )
    
    null_percent = total_pixels.subtract(valid_pixels) \
                               .divide(total_pixels) \
                               .multiply(100)
    
    return base_img.set({
        "nullPercent": null_percent
    })

def query_utm_crs_info(lon: float, lat: float) -> Tuple[float, float, str]:
    """
    Converts latitude and longitude coordinates to UTM coordinates and returns the UTM zone 
    and EPSG code for the projection.

    Args:
        lon (float): Longitude in decimal degrees.
        lat (float): Latitude in decimal degrees.

    Returns:
        Tuple[float, float, str]: UTM coordinates (x, y) and the corresponding EPSG code.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    zone_epsg = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return x, y, "EPSG:" + zone_epsg



def to_image(id_str: str) -> ee.Image:
    """
    Converts a string representing an image ID to an Earth Engine image object.

    Args:
        id_str (str): The image ID string.

    Returns:
        ee.Image: The Earth Engine image object corresponding to the input ID.
    """
    return ee.Image(id_str)




#################################
## Download NEON and S2 images ##
#################################

# ---------------------------------------------------------------------------------------------
# SpectralData class to manage everything
@dataclass
class SpectralData:
    image: ee.Image
    s2_table: pd.DataFrame
    bands_s2: list

    def __init__(self, image: ee.Image, s2_table: pd.DataFrame):
        self.image = image
        self.s2_table = s2_table
        self.bands_s2 = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B10", "B11", "B12"]

        # Prepare spectral bands and metadata for NEON
        self.bands_neon_select = [f"B{i:03d}" for i in range(1, 427)]
        self.band_metadata_neon = [f"WL_FWHM_{band}" for band in self.bands_neon_select]
        self.bands_neon_ee_select = ee.List(self.bands_neon_select)

        # Extract wavelengths for NEON bands from the image
        self.wavelength = ee.List([
            ee.Number.parse(
                ee.String(self.image.get(bandName)).split(",").get(0)
            ) for bandName in self.band_metadata_neon
        ])

    def get_wavelengths(self) -> ee.List:
        return self.wavelength
    
# Interpolation Functions
def _make_segment_dict(pair: ee.List) -> ee.Dictionary:
    pair = ee.List(pair)
    xvals = ee.List(pair.get(0))  # [x0, x1]
    yvals = ee.List(pair.get(1))  # [y0, y1]
    x0 = ee.Number(xvals.get(0))
    x1 = ee.Number(xvals.get(1))
    y0 = ee.Number(yvals.get(0))
    y1 = ee.Number(yvals.get(1))
    m = y1.subtract(y0).divide(x1.subtract(x0))
    return ee.Dictionary({'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'm': m})

def prepare_segments(x_values: ee.List, y_values: ee.List) -> ee.List:
    pairs = x_values.slice(0, -1).zip(x_values.slice(1))
    pairs = pairs.zip(y_values.slice(0, -1).zip(y_values.slice(1)))
    segments = pairs.map(lambda pair: _make_segment_dict(pair))
    return segments

def interpolate_one_x(segments: ee.List, xq: ee.Number) -> ee.Number:
    candidates = segments.map(
        lambda seg: ee.Algorithms.If(
            ee.Number(ee.Dictionary(seg).get('x0')).lte(xq).And(
                ee.Number(ee.Dictionary(seg).get('x1')).gte(xq)
            ),
            ee.Number(ee.Dictionary(seg).get('y0')).add(
                ee.Number(ee.Dictionary(seg).get('m'))
                  .multiply(xq.subtract(ee.Number(ee.Dictionary(seg).get('x0'))))
            ),
            None
        )
    )
    return ee.List(candidates).removeAll([None]).get(0)

def linear_interpolation(
        x_values: ee.List, 
        y_values: ee.List, 
        x_query: ee.List
    ) -> ee.List:
    segs = prepare_segments(x_values, y_values)
    result = x_query.map(lambda xq: interpolate_one_x(segs, ee.Number(xq)))
    return result

def create_interp1d(
        x_values: ee.List,
        y_values: ee.List,
        kind: str = 'linear'
    ) -> Callable[[ee.List], ee.List]:
    if kind != 'linear':
        raise ValueError("Only 'linear' supported.")
    def _interpolator(x_query: ee.List) -> ee.List:
        return linear_interpolation(x_values, y_values, x_query)
    return _interpolator


# Generalized function to generate S2 band from NEON
def generate_s2_band_from_neon(
        image_neon: ee.Image, 
        s2_table: pd.DataFrame, 
        band_name_s2: str, 
        wave_neon: ee.List, 
        bands_neon_ee_select: ee.List
    ) -> ee.Image:
    """
    Generate one band from NEON using interpolation and Sentinel-2 SRF from the table.
    """
    col_name = s2_table.columns[1][:-2] + band_name_s2
    mask = s2_table[col_name] != 0
    xvals = s2_table['SR_WL'][mask].astype(float).tolist()
    yvals = s2_table[col_name][mask].astype(float).tolist()
    s2_srfx = ee.List(xvals)
    s2_srfy = ee.List(yvals)
    x_min = min(xvals)
    x_max = max(xvals)
    widx = wave_neon.map(lambda w: ee.Number(w).gte(x_min).And(ee.Number(w).lte(x_max)))
    neon_srfx = (wave_neon.zip(widx)
                 .map(lambda pair: ee.Algorithms.If(
                     ee.List(pair).get(1), ee.List(pair).get(0), None
                 ))
                 .removeAll([None])
                )
    interp_fun = create_interp1d(s2_srfx, s2_srfy, 'linear')
    neon_srfx_interp = interp_fun(neon_srfx)
    sum_val = neon_srfx_interp.reduce(ee.Reducer.sum())
    neon_srfx_norm = neon_srfx_interp.map(lambda elem: ee.Number(elem).divide(sum_val))
    bands_filt = (bands_neon_ee_select.zip(widx)
                  .map(lambda pair: ee.Algorithms.If(
                      ee.List(pair).get(1), ee.List(pair).get(0), None
                  ))
                  .removeAll([None])
                 )
    selected_bands_img = image_neon.select(bands_filt)
    weights_img = ee.Image.constant(neon_srfx_norm)
    weighted_img = selected_bands_img.multiply(weights_img)
    final_single_band = weighted_img.reduce(ee.Reducer.sum()).rename(band_name_s2) # .round().toInt16()
    return final_single_band

# Generate all S2 bands and combine them into a single image
def generate_s2_image_from_neon(neon_id_image: str, s2_id_image: str) -> ee.Image:
    """
    Generates an image with 13 Sentinel-2 bands from NEON.
    """

    image = ee.Image(neon_id_image)
    image_s2 = ee.Image(s2_id_image)

    # Get spacecraft name to determine which Sentinel-2 table to use
    spacecraft_name = image_s2.get("SPACECRAFT_NAME")
    result = ee.Algorithms.If(
        ee.String(spacecraft_name).equals("Sentinel-2A"),
        "Sentinel-2A",
        ee.Algorithms.If(
            ee.String(spacecraft_name).equals("Sentinel-2B"),
            "Sentinel-2B",
            "Unknown"
        )
    )

    # Select appropriate Sentinel-2 SRF table
    type_s2 = result.getInfo()

    if type_s2 == "Sentinel-2A":
        s2_table_selected = pd.read_csv("https://raw.githubusercontent.com/JulioContrerasH/neon2s2/refs/heads/main/tables/srf_s2a.csv")
    elif type_s2 == "Sentinel-2B":
        s2_table_selected = pd.read_csv("https://raw.githubusercontent.com/JulioContrerasH/neon2s2/refs/heads/main/tables/srf_s2b.csv")
    else:
        s2_table_selected = None

    # Create SpectralData instance
    spectral_data = SpectralData(image=image, s2_table=s2_table_selected)
    print(spectral_data.bands_s2)

    final_bands = []
    for band in spectral_data.bands_s2:
        one_band_img = generate_s2_band_from_neon(spectral_data.image, spectral_data.s2_table, band, spectral_data.get_wavelengths(), spectral_data.bands_neon_ee_select)
        final_bands.append(one_band_img)
        print(f"Generated band {band}")

    final_s2_like_image = ee.Image(final_bands).rename(list(spectral_data.bands_s2))

    return final_s2_like_image
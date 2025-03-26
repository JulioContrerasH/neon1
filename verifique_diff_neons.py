import pathlib
import pandas as pd
import rasterio as rio
import tacotoolbox
import tacoreader
import rasterio as rio
import datetime
import ee

# Authenticate and initialize Google Earth Engine
ee.Authenticate()
ee.Initialize(project="ee-contrerasnetk") # change it


ROOT_DIR = pathlib.Path("/data/databases/legacy/OLD_SEN2NAIP/SuperSR")
table = pd.read_csv("/media/disk/users/julio/downloads_gee_neon/neon1/tables/neon_s2_all_2_images_pairs_updated.csv")


table["dir_try"] = table["neon_root_path"].apply(lambda p: pathlib.Path(p).parent)


import rasterio
from pathlib import Path

def get_max_pixel_value(file_path):
    """Obtiene el valor máximo de la primera banda de un archivo TIFF."""
    with rasterio.open(file_path) as src:
        band1 = src.read(1)  # Leer la primera banda
        return band1.max()  # Devuelve el valor máximo de los píxeles en esa banda

def compare_max_values_in_directory(directory):
    """Compara el valor máximo de la primera banda de los archivos .tif en un directorio."""
    tif_files = list(directory.glob("*.tif"))
    
    if len(tif_files) == 2:  # Aseguramos que hay exactamente 2 archivos .tif
        max_values = [(file.name, get_max_pixel_value(file)) for file in tif_files]
        return max_values
    else:
        return None

# Crear una nueva columna con los valores máximos de la primera banda de cada archivo .tif
table["max_pixel_values"] = table["dir_try"].apply(
    lambda dir_path: compare_max_values_in_directory(Path(dir_path))
)

# Filtrar los directorios donde los valores máximos son diferentes entre los dos archivos .tif
different_max_values = table[table["max_pixel_values"].apply(
    lambda values: values is not None and values[0][1] != values[1][1]
)]

# Mostrar solo las rutas de los directorios con valores máximos diferentes
print(different_max_values["dir_try"])

import pandas as pd
import pathlib
from osgeo import gdal
from typing import Union
from utils import *

table = pd.read_csv("tables/neon_s2_all_2_images_pairs.csv") 

# For NEON
root_path = pathlib.Path("/data/databases/legacy/OLD_SEN2NAIP/SuperSR")
table["neon_root_dir"] = root_path / "neon" / table["folder"] / table["neon_id"] / table["neon_ids"]
table["neon_root_path"] = table["neon_root_dir"].apply(warp_neon_dir)

# For S2
root_path = pathlib.Path("/data/databases/legacy/OLD_SEN2NAIP/SuperSR")
table["s2_root_path_prev"] = root_path / "s2" / table["folder"] / table["neon_id"] / (table["neon_ids"] + ".tiff")
table["s2_root_path"] = root_path / "sentinel2" / table["folder"] / table["neon_id"] / (table["neon_ids"] + ".tif")

table.apply(
    lambda row: warp_single_tif(
        row["s2_root_path_prev"], 
        row["s2_root_path"]
    ), 
    axis=1
),

table.to_csv("tables/neon_s2_all_2_images_pairs_updated.csv", index=False)









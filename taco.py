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

ROOT_DIR = pathlib.Path("/data/databases/legacy/OLD_SEN2NEON")
table = pd.read_csv("tables/neon_s2_all_2_images_pairs_updated.csv")
table["neon_root_path"] = table["neon_root_path"].str.replace(
    "OLD_SEN2NAIP/SuperSR", 
    "OLD_SEN2NEON"
)
table["s2_root_path"] = table["s2_root_path"].str.replace(
    "OLD_SEN2NAIP/SuperSR", 
    "OLD_SEN2NEON"
)
table["idx_occ"] = table.groupby("folder").cumcount()
table["tortilla_path"] = (
    ROOT_DIR.as_posix() + "/tortillas/" + table["folder"] + "_"  + table["idx_occ"].astype(str).str.zfill(2) + ".tortilla"
)

# table.to_csv("tables/neon_s2_all_2_images_pairs_updated.csv", index=False)

# Iterate over rows of the metadata table to process each image
for i, row in table.iterrows():
    
    # Print progress every 100 rows
    if i % 100 == 0:
        print(f"Processing {i}/{len(table)}")

    # Load profiles and metadata for the low-resolution (LR) image
    profile_lr = rio.open(row["s2_root_path"]).profile
    sample_lr = tacotoolbox.tortilla.datamodel.Sample(
        id="lr",
        path=row["s2_root_path"],
        file_format="GTiff",
        data_split="train",
        stac_data={
            "crs": "EPSG:" + str(profile_lr["crs"].to_epsg()),
            "geotransform": profile_lr["transform"].to_gdal(),
            "raster_shape": (profile_lr["height"], profile_lr["width"]),
            "time_start": datetime.datetime.strptime(row.s2_date, '%Y-%m-%d'),
            "time_end": datetime.datetime.strptime(row.s2_date, '%Y-%m-%d'),
            "centroid": f"POINT ({row['lon_c']} {row['lat_c']})"
        },
        s2_id_gee=row["s2_id_gee"],
        cloud_perc=((1 - row["cs_cdf"]) * 100)
    )

    # Load profiles and metadata for the high-resolution (HR) image
    profile_hr = rio.open(row["neon_root_path"]).profile
    sample_hr = tacotoolbox.tortilla.datamodel.Sample(
        id="hr",
        path=row["neon_root_path"],
        file_format="GTiff",
        data_split="train",
        stac_data={
            "crs": "EPSG:" + str(profile_hr["crs"].to_epsg()),
            "geotransform": profile_hr["transform"].to_gdal(),
            "raster_shape": (profile_hr["height"], profile_hr["width"]),
            "time_start": datetime.datetime.strptime(row.neon_date, '%Y-%m-%d'), 
            "time_end": datetime.datetime.strptime(row.neon_date, '%Y-%m-%d'), 
            "centroid": f"POINT ({row['lon_c']} {row['lat_c']})"
        },
        s2_id_gee = row["neon_id_gee"],
        neon_val_null = row["neon_val_null"]
    )

    # Create a set of samples for each image type (LR, HR, mask, harmonized LR and HR)
    samples = tacotoolbox.tortilla.datamodel.Samples(
        samples=[
            sample_lr,
            sample_hr
        ]
    )

    # Create the tortilla (data object) for this row
    tacotoolbox.tortilla.create(samples, row["tortilla_path"], quiet=True)

# Process tortilla files and append corresponding metadata
sample_tortillas = []

for index, row in table.iterrows():
    
    # Print progress every 100 rows
    if index % 100 == 0:
        print(f"Processing {index}/{len(table)}")

    # Load tortilla data for each row
    sample_data = tacoreader.load(row["tortilla_path"])
    sample_data = sample_data.iloc[1]

    # Create a sample for the tortilla data
    sample_tortilla = tacotoolbox.tortilla.datamodel.Sample(
        id=pathlib.Path(row["tortilla_path"]).stem,
        path=row["tortilla_path"],
        file_format="TORTILLA",
        stac_data={
            "crs": sample_data["stac:crs"],
            "geotransform": sample_data["stac:geotransform"],
            "raster_shape": sample_data["stac:raster_shape"],
            "centroid": sample_data["stac:centroid"],
            "time_start": sample_data["stac:time_start"],
            "time_end": sample_data["stac:time_end"],
        },
        days_diff=row["abs_days_diff"],
        neon_val_null = row["neon_val_null"]
    )    
    sample_tortillas.append(sample_tortilla)

# Create a collection of all tortilla samples
samples = tacotoolbox.tortilla.datamodel.Samples(
    samples=sample_tortillas
)

# Add RAI metadata to footer (used for further data processing)
samples_obj = samples.include_rai_metadata(
    sample_footprint=5160, # extension in meters
    cache=False,  # Set to True for caching
    quiet=False  # Set to True to suppress the progress bar
)


description = """

## Description

### Dataset

A dataset of paired Sentinel-2 multispectral images and NEON hyperspectral imagery for validating super-resolución (SR) algorithms. Each pair consists of a Sentinel-2 image at 10 m resolution and a spatially and temporally aligned NEON image at 2.5 m resolution (resampled from original 1 m). The NEON sensor provides high-resolution “ground truth” reflectance to upscale Sentinel-2 imagery from 10 m to 2.5 m, covering the same spectral bands as Sentinel-2 (except the cirrus band B10). This resource enables development and benchmarking of SR methods to enhance Sentinel-2 imagery using real airborne hyperspectral data.


**Sentinel-2 MSI:** Sentinel-2 is a twin-satellite mission (2A/2B) providing optical imagery with 13 spectral bands spanning visible, near-infrared (VNIR) and shortwave-infrared (SWIR) wavelengths. The Multispectral Instrument (MSI) samples four bands at 10 m, six bands at 20 m, and three bands at 60 m spatial resolution. Sentinel-2’s bands cover 443 nm (coastal aerosol) to 2202 nm (SWIR), supporting applications in vegetation monitoring, water resources, land cover and more. The mission offers global land coverage every ~5 days (with both satellites) and a free, open data policy. In this dataset, Sentinel-2 Level-2A surface reflectance images are used as the **low-resolution (LR)** input.

**NEON Hyperspectral Imagery:** The National Ecological Observatory Network (NEON) collects airborne hyperspectral data via the NEON Imaging Spectrometer (NIS), an instrument based on NASA’s AVIRIS-NG design. The NIS is a **visible-to-SWIR imaging spectrometer** measuring reflected solar radiance from ~380 nm to 2510 nm in ~5 nm bands, yielding ~426 contiguous spectral bands. The sensor’s Mercury-Cadmium-Telluride detector array (480×640 px) provides ~1 m native spatial resolution and is thermally cooled for high signal-to-noise. After calibration and atmospheric correction, NEON releases **surface reflectance image cubes** (Level 2 data product DP3.30006.001) with 1 m pixels and 426 spectral bands. Wavelength regions dominated by atmospheric water vapor (1340–1445 nm and 1790–1955 nm) contain no valid surface data and are flagged (fill value). Notably, this includes Sentinel-2’s cirrus Band 10 (~1375 nm) which NEON cannot observe due to atmospheric absorption, explaining its exclusion from this dataset.

### Sensors used


- **Sentinel-2 MSI (Multispectral Instrument):** Optical imager on ESA’s Sentinel-2A/2B satellites in sun-synchronous orbit (~10:30 am descending node). 13 bands spanning 443–2190 nm at 10 m, 20 m, 60 m resolutions. Radiometric resolution: 12-bit. The MSI is a pushbroom sensor with three detectors for different resolution groups, which means the 10 m, 20 m, 60 m bands are acquired with slight time offsets. In L2A products, data are atmospherically corrected to surface reflectance (using Sen2Cor). Sentinel-2 data used here are Level-2A with UTM projection, provided by Copernicus Open Access Hub/USGS Earth Explorer. Each image tile covers 100×100 km; our 5.12 km subsets were cropped from these tiles.

- **NEON Airborne Observation Platform (AOP) – Hyperspectral Sensor (NIS, “AVIRIS-NG”):** A high-fidelity imaging spectrometer flown on a light aircraft (e.g., Twin Otter). Collects contiguous spectral bands (~426 bands) from 380–2510 nm with ~5 nm sampling, ~7.5 nm FWHM, using a diffraction grating and MCT detector array. Typical flight altitude ~1000 m AGL yields 1 m ground sampling distance; swath ~1 km. NEON operates three identical NIS units built by NASA JPL . Data is delivered as “Level 1” at-sensor radiance and “Level 2” surface reflectance (after calibración radiométrica, corrección atmosférica y geométrica). Radiometric resolution: 14-bit (digital numbers) converted to physical units. SNR is typically > 100:1 in VNIR and lower in SWIR at full resolution. The NEON data used were downloaded via the NEON Data Portal or via Google Earth Engine. Each NEON flight campaign covers the nominal 1 km × 1 km field site and surrounding area; our 5.12 km subsets may include multiple NEON flight lines mosaicked (NEON provides seamless mosaics per site/year).

By leveraging these two sensors, the dataset combines **satellite multi-spectral imagery** (broad coverage, lower spatial resolution) with **airborne hyperspectral imagery** (local coverage, high spatial and spectral resolution). This fusion enables advanced research in image super-resolution and spectral-spatial data integration.

"""

bibtex_1 = """
@article{Kampe2010,
  author    = {Kampe, Thomas U. and Johnson, Brian R. and Kuester, Michele and Keller, Michael},
  title     = {{NEON: the first continental-scale ecological observatory with airborne remote sensing of vegetation canopy biochemistry and structure}},
  journal   = {Journal of Applied Remote Sensing},
  volume    = {4},
  pages     = {043510},
  year      = {2010},
  doi       = {10.1117/1.3361375},
  publisher = {SPIE}
}
"""
bibtex_2 = """
@article{Scholl2020,
  author    = {Scholl, Victoria M. and Cattau, Megan E. and Joseph, Maxwell B. and Balch, Jennifer K.},
  title     = {Integrating National Ecological Observatory Network (NEON) airborne remote sensing and in-situ data for optimal tree species classification},
  journal   = {Remote Sensing},
  volume    = {12},
  number    = {9},
  pages     = {1414},
  year      = {2020},
  doi       = {10.3390/rs12091414}
}
"""

# Create a collection object with metadata for the dataset
collection_object = tacotoolbox.datamodel.Collection(
    id="sen2neon",
    title="SEN2NEON: Sentinel-2 & NEON Hyperspectral Super-Resolution Dataset",  # Update title accordingly
    dataset_version="1.0.0", # Update version accordingly
    description=description,  # Update description accordingly
    licenses=["cc-1.0"], 
    extent={
        "spatial": [[-170.0, 15.0, -65.0, 72.0]],  # Define spatial extent
        "temporal": [["2013-01-01T00:00:00Z", "2024-09-08T16:03:42Z"]]  # Define temporal extent
    },
    providers=[{
        "name": "National Ecological Observatory Network (NEON)",  # Update provider name
        "roles": ["host"],
        "links": [
            {
                "href": "https://data.neonscience.org/",
                "rel": "source",
                "type": "text/html"
            }
        ],
    }],
    keywords=["remote-sensing", "super-resolution", "deep-learning", "sentinel-2", "NEON"],
    task="super-resolution",
    curators=[
        {
            "name": "Julio Contreras",
            "organization": "Image & Signal Processing",
            "email": ["julio.contreras@uv.es"],
            "links": [
                {
                    "href": "https://juliocontrerash.github.io/",
                    "rel": "homepage",
                    "type": "text/html"
                }
            ],
        }
    ],
    split_strategy="none", 
    discuss_link={
        "href": "https://huggingface.co/datasets/tacofoundation/sen2neon/discussions",
        "rel": "source",
        "type": "text/html"
    },
    raw_link={
        "href": "https://huggingface.co/datasets/tacofoundation/sen2neon",
        "rel": "source",
        "type": "text/html"
    },
    optical_data={"sensor": "sentinel2msi"}, # neon-ais
    labels={
        "label_classes": [],
        "label_description": "No labeled classes. This dataset is intended for super-resolution tasks."
    },
    scientific={
        "doi": "10.9999/zenodo.placeholder_sen2neon",
        "citation": "SEN2NEON dataset, to be assigned official DOI in the future.",
        "summary": "SEN2NEON merges Sentinel-2 (ESA) and NEON hyperspectral data for super-resolution research. Public domain (CC0).",
        "publications": [
            {
                "doi": "10.1117/1.3361375",
                "citation": bibtex_1,
                "summary": "Kampe et al. (2010): Foundational paper on NEON's airborne instrumentation.",
            },
            {
                "doi": "10.3390/rs12091414",
                "citation": bibtex_2,
                "summary": "Scholl et al. (2020): Demonstrates NEON data usage in tree species classification.",
            }
        ]
    }
)

# Get the path of the tortilla file and create the directory if needed
full_path = table["tortilla_path"].iloc[0]
directory = pathlib.Path(full_path).parent.parent / "tacos"


# Generate the final output file using the samples and collection objects
output_file = tacotoolbox.create(
    samples=samples_obj,
    collection=collection_object,
    output= directory / "sen2neon.taco"
)
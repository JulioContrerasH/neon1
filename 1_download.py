import pandas as pd
import ee
import re
import pathlib
from utils import *
import concurrent.futures

ee.Initialize()

dataframe = pd.read_csv("tables/neon_s2_all_2_images_pairs.csv")

for i, row in dataframe.iterrows():
    
    x = float(row['x'])
    y = float(row['y'])

    image =  generate_s2_image_from_neon(row['neon_id_gee'], row['s2_id_gee'])
    request = {
        'expression': image,
        'fileFormat': 'GeoTIFF',
        'bandIds': ['B1', 'B2', 'B3', "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12"],
        'grid': {
            'dimensions': {
                'width': 2064 ,
                'height': 2064 
            },
            'affineTransform': {
                'scaleX': 2.5,
                'shearX': 0,
                'translateX': x,
                'shearY': 0,
                'scaleY': -2.5,
                'translateY': y
            },
            'crsCode': row['epsg']
        }
    }

    try:
        image = ee.data.computePixels(request)
    except ee.ee_exception.EEException as ee_error:
        ee_error_message = str(ee_error)

    match = re.findall(r'\d+', ee_error_message)
    image_pixel = match[0]
    max_pixel = match[1]
    images = int(image_pixel) / int(max_pixel)

    power = 0  # Comienza con 4^0
    while images > 1:
        power += 1
        images = int(image_pixel) / (int(max_pixel) * 4**power)
        val_split = 4**power

    print(f"Generar {val_split} geotransforms")


    request_list = []
    cell_width = 2064 // 2**power  # 640
    cell_height = 2064 // 2**power  # 640

    for v in range(2**power):  # Fila
        print(v)
        for j in range(2**power):  # Columna
            # Calcular las nuevas coordenadas de x e y
            new_x = x + (j * cell_width * 2.5)
            new_y = y - (v * cell_height * 2.5)  # Negativo porque la coordenada Y crece hacia arriba

            # Crear el request para cada subcuadro
            subrequest = {
                'expression': image,
                'fileFormat': 'GeoTIFF',
                'bandIds': ['B1', 'B2', 'B3', "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12"],
                'grid': {
                    'dimensions': {
                        'width': cell_width,
                        'height': cell_height
                    },
                    'affineTransform': {
                        'scaleX': 2.5,
                        'shearX': 0,
                        'translateX': new_x,
                        'shearY': 0,
                        'scaleY': -2.5,
                        'translateY': new_y
                    },
                    'crsCode': row['epsg'],
                }
            }

            # Agregar el subrequest a la lista
            request_list.append(subrequest)


    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_list = []
        
        for n, ulist in enumerate(request_list):
            # Calcula el path de salida
            dir = pathlib.Path(f"/data/databases/legacy/OLD_SEN2NAIP/SuperSR/neon_tif/{row['folder']}/{row['neon_id']}/{row['neon_ids']}")
            dir.mkdir(parents=True, exist_ok=True)
            full_outname = dir / f"{n:03d}.tif"

            # Envía la tarea al ThreadPool
            future = executor.submit(fetch_and_save, ulist, full_outname)
            future_list.append(future)

        # Opcional: esperar a que terminen todas y/o manejar errores
        for future in concurrent.futures.as_completed(future_list):
            # Si quieres capturar excepciones individualmente:
            try:
                future.result()  
            except Exception as e:
                print(f"Error en una de las descargas: {e}")
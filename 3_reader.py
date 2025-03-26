import tacoreader
import rasterio as rio
import matplotlib.pyplot as plt

dataset = tacoreader.load("tacofoundation:sen2neon")

# Read a sample row
idx = 273
row = dataset.read(idx)
row_id = dataset.iloc[idx]["tortilla:id"]

# Retrieve the data
lr, hr = row.read(0), row.read(1)
with rio.open(lr) as src_lr, rio.open(hr) as src_hr:
    lr_data = src_lr.read([2, 3, 4]) # Blue, Green, Red of Sentinel-2
    hr_data = src_hr.read([2, 3, 4]) # Blue, Green, Red of Neon

# Display
fig, ax = plt.subplots(1, 2, figsize=(10, 5.5))
ax[0].imshow(lr_data.transpose(1, 2, 0) / 2000)
ax[0].set_title(f'LR_{row_id}')
ax[0].axis('off')
ax[1].imshow(hr_data.transpose(1, 2, 0) / 2000) 
ax[1].set_title(f'HR_{row_id}')
ax[1].axis('off')
plt.tight_layout()
plt.show()
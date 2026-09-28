import pandas as pd

# Enlace de descarga directa generado con el ID de tu archivo
file_id = '1Pvje1lB0tpvl6yMSYi9HDxsdbtVw63L6'
url = f'https://drive.google.com/uc?id={file_id}&export=download'

# Cargar el dataset directamente en pandas
df = pd.read_parquet(url)

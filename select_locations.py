import pandas as pd
import os
import glob
  
path = "./data/csv"
csv_files = glob.glob(os.path.join(path, "*.csv"))
  
result = []
for f in csv_files:
    df = pd.read_csv(f)
    n = f.split('\\')[-1].split('.')[0].replace('vegetation_stats_area_', '')
    df.set_index('MVS_NAME', inplace=True)
    total = df['Shape_Area'].sum()
    tussok = df.loc['Temperate tussock grasslands']['Shape_Area']
    percent = tussok / total
    result.append([n, total, tussok, percent])

#### transpose
df = pd.DataFrame(result)
# df = df.transpose()
df.columns = ['Area', 'Shape_Area', 'Tussok', 'percent']
print(df)
df.to_csv("final.csv")
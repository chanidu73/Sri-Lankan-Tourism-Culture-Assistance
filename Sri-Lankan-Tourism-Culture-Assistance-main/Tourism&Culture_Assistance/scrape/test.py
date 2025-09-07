import pandas as pd

df = pd.read_json("nomadicmatt_srilanka.json")# , lines=True)

print(df.head())
print(df.info())
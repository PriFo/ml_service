import pandas as pd
import seaborn as sns
from dython.nominal import associations  # ← Правильная функция
import matplotlib.pyplot as plt
import numpy as np

# Загрузка данных
data = pd.read_csv('C:/Users/screb/Desktop/1cbit/ml_service/ml_service/datasets/dataset_20k_generated.csv')

# Заполняем пропуски
data_filled = data.fillna('missing')

print("Столбцы:", data_filled.columns.tolist())
print("Размер:", data_filled.shape)

# Cramér's V через associations()
corr_matrix = associations(
    data_filled, 
    nominal_columns='all',  # Все колонки категориальные
    filename=False,         # Не сохранять файл
    cmap='coolwarm'
)

# Heatmap из результата
plt.figure(figsize=(12, 10))
sns.heatmap(
    corr_matrix['corr'], 
    annot=True, 
    cmap='RdBu_r', 
    center=0,
    fmt='.2f',
    square=True
)
plt.title('Cramér\'s V: Ассоциации между категориями')
plt.tight_layout()
plt.show()

# Топ ассоциаций с label
label_corr = corr_matrix['corr']['label'].sort_values(ascending=False)
print("\nТоп-5 ассоциаций с label:")
print(label_corr.head())
# data_processor.py
import pandas as pd
import matplotlib.pyplot as plt

def analyze_data(csv_file='../datos/sensores_completos.csv'):
    """Analizar y graficar datos"""
    try:
        df = pd.read_csv(csv_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        print("Resumen de datos:")
        print(df.describe())
        
        # Gráficos
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        plt.plot(df['timestamp'], df['spo2'])
        plt.title('Nivel de oxigenación en la sangre')
        plt.xticks(rotation=45)
        
        plt.subplot(2, 2, 2)
        plt.plot(df['timestamp'], df['acel_x'], label='X')
        plt.plot(df['timestamp'], df['acel_y'], label='Y')
        plt.plot(df['timestamp'], df['acel_z'], label='Z')
        plt.title('Aceleración')
        plt.legend()
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.show()
        
    except FileNotFoundError:
        print("Archivo de datos no encontrado")

if __name__ == "_main_":
    analyze_data()
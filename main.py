import tkinter as tk
from tkinter import ttk, messagebox
import cv2 as cv       
import serial        
import time
import os
import threading
import sys
import functions
import json

def main():
    with open("cfg.json", "r") as file:
        data = json.load(file)
        
    # Diretório para salvar as imagens
    DIR_IMG = "TT1/"
    os.makedirs(DIR_IMG, exist_ok=True)
    
    # Configurações do GRBL e porta serial
    PORT = data["port"]        # Porta de comunicação com Arduino/GRBL
    BAUDRATE = data["baudrate"]     # Taxa de transferência - padrão GRBL
    
    # Dados das plantas
    ID_PLANT = [plant["id"] for plant in data["plants"]]
    POS_X_PLANT = [plant["X"] for plant in data["plants"]]
    POS_Y_PLANT = [plant["Y"] for plant in data["plants"]]
    
    # Inicializa câmera e conexão serial (serão definidos na função init_system)
    cam = None
    grbl = None
    
    # Tempo de espera para conclusão dos movimentos (em segundos)
    MOVE_DELAY = 10
    
    # Criação da janela principal
    root = tk.Tk()
    root.title("Interface CNC + Camera USB")
    root.geometry("500x600")
    
    # Frame para configurações gerais
    frame_config = ttk.LabelFrame(root, text="Configurações")
    frame_config.pack(padx=10, pady=10, fill="x")
    
    # Campo para definir a velocidade (F)
    ttk.Label(frame_config, text="Velocidade (F):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    speed_entry = ttk.Entry(frame_config, width=10)
    speed_entry.insert(0, "7000")  
    speed_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    
    # Frame para os botões das plantas
    frame_plants = ttk.LabelFrame(root, text="Seleção de Planta")
    frame_plants.pack(padx=10, pady=10, fill="both", expand=True)
    
    # Cria botões para cada planta (B01 a B12) organizados em duas colunas
    for i, plant_id in enumerate(ID_PLANT):
        btn = ttk.Button(frame_plants, text=plant_id, command=lambda idx=i: functions.executar_planta(idx, grbl, speed_entry, POS_X_PLANT, POS_Y_PLANT, DIR_IMG, ID_PLANT,
                                                                                                      MOVE_DELAY))
        # Distribui os botões em 2 colunas
        row = i // 2
        col = i % 2
        btn.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
    
    # Botão para encerrar o sistema
    btn_close = ttk.Button(root, text="Fechar Sistema", command=lambda: functions.close_system(grbl, cam))
    btn_close.pack(pady=10)
    
    # Inicializa o sistema (câmera e GRBL) antes de iniciar a interface
    functions.init_system(DIR_IMG, ID_PLANT, PORT, BAUDRATE)
    
    # Inicia a interface gráfica
    root.protocol("WM_DELETE_WINDOW", lambda: functions.close_system(grbl, cam))
    root.mainloop()

if __name__ == "__main__":
    main()
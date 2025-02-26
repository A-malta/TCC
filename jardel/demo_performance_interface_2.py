"""
PROBLEMAS:
[  ] O comportamento de coleta ao selcionar plantas não é o esperado
[  ] A barra de progrsso deve considerar apenas as 12 plantas e desconsiderar o B00
e no caso da seleção de plantas estar ativa a barra deve considerar quantas plantas estão selecionadas
[  ] O caminhamento está comprometido mesmo no 'Coletar todas as plantas', deve apenas caminhar sobre 
todas as plantas seguindo a órdem do JSON e eliminar a B00 ao final da coleta
[  ] O caminhamento parece estar somado a 1, experikmente coletrar B12 e B06
"""

import cv2 as cv
import serial
import time
import os
import json
import signal
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk
import threading
import queue
from datetime import datetime


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle GRBL e Captura de Imagens")
        self.root.geometry("1000x700")

        self.root.protocol("WM_DELETE_WINDOW", self.confirm_close)

        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_frame = ttk.Frame(self.main_frame)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_label = ttk.Label(self.log_frame, text="Log de Saída")
        self.log_label.pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, height=10, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(
            self.log_frame, text="Status: Aguardando inicialização...")
        self.status_label.pack(anchor=tk.W, pady=5)

        self.progress_frame = ttk.Frame(self.log_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)
        self.progress_label = ttk.Label(self.progress_frame, text="Progresso:")
        self.progress_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, length=500, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_text = ttk.Label(self.progress_frame, text="0.0% (0/12)")
        self.progress_text.pack(side=tk.LEFT, padx=5)

        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.selection_frame = ttk.Frame(self.left_frame)
        self.selection_frame.pack(fill=tk.Y)

        self.header_frame = ttk.Frame(self.selection_frame)
        self.header_frame.pack(fill=tk.X)
        self.plant_label = ttk.Label(
            self.header_frame, text="Selecione as Plantas:")
        self.plant_label.pack(side=tk.LEFT)
        self.image_label = ttk.Label(
            self.header_frame, text="Imagem Atual: Nenhuma planta selecionada")
        self.image_label.pack(side=tk.LEFT, padx=10)

        with open("cfg.json", "r") as file:
            data = json.load(file)
        self.ID_PLANT = [plant["id"] for plant in data["plants"]]
        self.POS_X_PLANT = [plant["X"] for plant in data["plants"]]
        self.POS_Y_PLANT = [plant["Y"] for plant in data["plants"]]

        self.plant_selected = {plant_id: False for plant_id in self.ID_PLANT}
        self.plant_buttons = {}

        self.column3_frame = ttk.Frame(self.selection_frame)
        self.column3_frame.pack(side=tk.LEFT, padx=5)
        self.column4_frame = ttk.Frame(self.selection_frame)
        self.column4_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.column3_frame, text="Bloco 3").pack(anchor=tk.W)
        ttk.Label(self.column4_frame, text="Bloco 4").pack(anchor=tk.W)

        # Ordem invertida mantida como especificado
        for plant_id in ["B12", "B11", "B10", "B09", "B08", "B07"]:
            if plant_id in self.ID_PLANT:
                btn = ttk.Button(
                    self.column3_frame,
                    text=plant_id,
                    width=6,
                    command=lambda pid=plant_id: self.toggle_plant(pid)
                )
                btn.pack(pady=5)
                self.plant_buttons[plant_id] = btn

        for plant_id in ["B06", "B05", "B04", "B03", "B02", "B01"]:
            if plant_id in self.ID_PLANT:
                btn = ttk.Button(
                    self.column4_frame,
                    text=plant_id,
                    width=6,
                    command=lambda pid=plant_id: self.toggle_plant(pid)
                )
                btn.pack(pady=5)
                self.plant_buttons[plant_id] = btn

        self.control_frame = ttk.Frame(self.left_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        self.start_button = ttk.Button(
            self.control_frame, text="Iniciar", command=self.start_process)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(
            self.control_frame, text="Cancelar", command=self.cancel, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        self.close_button = ttk.Button(
            self.control_frame, text="Fechar", command=self.confirm_close)
        self.close_button.pack(side=tk.LEFT, padx=5)

        self.image_frame = ttk.Frame(self.main_frame)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.image_frame, width=640, height=360)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.grbl = None
        self.cam = None
        self.dir_img = None
        self.running = False
        self.thread = None
        self.queue = queue.Queue()
        self.root.after(100, self.process_queue)

        signal.signal(signal.SIGINT, self.signal_handler)

    def process_queue(self):
        while True:
            try:
                task = self.queue.get_nowait()
                task()
            except queue.Empty:
                break
        self.root.after(100, self.process_queue)

    def log(self, message):
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"

        def task():
            self.log_text.insert(tk.END, log_entry + "\n")
            self.log_text.see(tk.END)
            self.root.update_idletasks()
            with open("log.txt", "a") as log_file:
                log_file.write(log_entry + "\n")
        self.queue.put(task)

    def update_status(self, status):
        def task():
            self.status_label.config(text=f"Status: {status}")
        self.queue.put(task)

    def update_progress(self, current, total):
        def task():
            percent = (current / total) * 100 if total > 0 else 0
            self.progress_bar['value'] = percent
            self.progress_text.config(
                text=f"{percent:.1f}% ({current}/{total})")
            self.root.update_idletasks()
        self.queue.put(task)

    def update_image(self, frame, plant_name):
        def task():
            frame_resized = cv.resize(frame, (640, 360))
            img = cv.cvtColor(frame_resized, cv.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            photo = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas.image = photo
            self.image_label.config(text=f"Imagem Atual: {plant_name}")
            self.root.update_idletasks()
        self.queue.put(task)

    def toggle_plant(self, plant_id):
        self.plant_selected[plant_id] = not self.plant_selected[plant_id]
        btn = self.plant_buttons[plant_id]
        if self.plant_selected[plant_id]:
            btn.configure(style="Selected.TButton")
        else:
            btn.configure(style="TButton")
        self.log(
            f"Planta {plant_id} {'selecionada' if self.plant_selected[plant_id] else 'desselecionada'}")

    def signal_handler(self, sig, _):
        self.log("===============================================================")
        self.log("Interrupção detectada (Ctrl + C). Finalizando...")
        self.log("===============================================================")
        self.finalize()

    def cancel(self):
        self.log("===============================================================")
        self.log("Cancelamento solicitado. Finalizando...")
        self.log("===============================================================")
        self.finalize()

    def confirm_close(self):
        if messagebox.askyesno("Confirmar Fechamento", "Tem certeza que deseja fechar o programa?"):
            self.log(
                "===============================================================")
            self.log("Fechamento solicitado pelo usuário. Finalizando...")
            self.log(
                "===============================================================")
            self.finalize()
            self.root.quit()

    def finalize(self):
        self.log("--- Fechando conexão... ---")
        if self.grbl:
            try:
                self.grbl.close()
                self.log("Conexão GRBL fechada.")
            except Exception as e:
                self.log(f"Erro ao fechar GRBL: {e}")
            self.grbl = None
        if self.cam:
            try:
                self.cam.release()
                self.log("Câmera liberada.")
            except Exception as e:
                self.log(f"Erro ao liberar câmera: {e}")
            self.cam = None
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.image_label.config(
            text="Imagem Atual: Nenhuma planta selecionada")

    def send_grbl(self, cmd):
        self.grbl.write((cmd + "\r\n").encode())
        while True:
            if self.grbl.inWaiting() > 0:
                response = self.grbl.readline().decode().strip()
                self.log(f"Enviando: {cmd} | Resposta: {response}")
                if "ok" in response or "error" in response:
                    break
            time.sleep(0.01)

    def wait_for_idle(self, timeout=30):
        start_time = time.time()
        while self.running:
            if time.time() - start_time > timeout:
                self.log("Timeout esperando pelo estado 'Idle'. Abortando...")
                self.running = False
                break
            self.grbl.write(b"?")
            time.sleep(0.1)
            if self.grbl.inWaiting() > 0:
                status = self.grbl.readline().decode().strip()
                self.update_status(status)
                self.log("Status: " + status)
                if "<Idle" in status:
                    break

    def get_image(self, plant_idx, timestamp):
        ret, frame = self.cam.read()
        if not ret:
            self.log(
                f"Erro ao capturar imagem para {self.ID_PLANT[plant_idx]}")
            return
        self.update_image(frame, self.ID_PLANT[plant_idx])
        frame_resized = cv.resize(frame, (640, 360))
        nome = os.path.join(
            self.dir_img, f"{timestamp}_{self.ID_PLANT[plant_idx]}.jpg")
        cv.imwrite(nome, frame)
        self.log(f"Imagem capturada e salva como {nome}")

    def start_process(self):
        if self.running:
            return

        # Índices das plantas selecionadas (exclui B00 inicialmente)
        selected_indices = [
            i for i, plant_id in enumerate(self.ID_PLANT)
            if self.plant_selected.get(plant_id, False) and plant_id != "B00"
        ]

        # Se nada for selecionado, processa todas as plantas exceto B00
        if not selected_indices:
            selected_indices = [i for i in range(
                len(self.ID_PLANT)) if self.ID_PLANT[i] != "B00"]
            self.log(
                "Nenhuma planta selecionada. Processando todas as plantas (exceto B00) como padrão.")
        else:
            self.log(
                f"Processando {len(selected_indices)} plantas selecionadas: {[self.ID_PLANT[i] for i in selected_indices]}")

        # Ordena em ordem decrescente (B12 -> B01)
        selected_indices = sorted(selected_indices, reverse=True)

        # Adiciona B00 como primeira planta se todas estiverem sendo processadas
        b00_idx = self.ID_PLANT.index("B00") if "B00" in self.ID_PLANT else -1
        if b00_idx != -1 and len(selected_indices) == len(self.ID_PLANT) - 1:
            selected_indices = [b00_idx] + selected_indices

        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.running = True
        self.thread = threading.Thread(
            target=self.run_process, args=(selected_indices,))
        self.thread.daemon = True
        self.thread.start()

    def run_process(self, selected_indices):
        self.grbl = None
        self.cam = None

        # Cria uma pasta com timestamp para a operação
        timestamp = datetime.now().strftime("%d_%m_%Y__%H_%M_%S")
        self.dir_img = os.path.join("TT2", timestamp)
        if not os.path.exists(self.dir_img):
            os.makedirs(self.dir_img)

        with open("cfg.json", "r") as file:
            data = json.load(file)

        PORT = data["port"]
        BAUDRATE = data["baudrate"]

        self.log("Iniciando comunicação GRBL...")
        try:
            self.grbl = serial.Serial(PORT, BAUDRATE, timeout=1)
            time.sleep(2)
            self.grbl.write(b"\r\n\r\n")
            time.sleep(2)
            self.grbl.flushInput()
            self.log("Conectado ao GRBL na porta: " + PORT)
        except Exception as e:
            self.log("Erro ao conectar na porta: " + str(e))
            self.finalize()
            return

        self.log("-> Iniciando Camera...")
        self.cam = cv.VideoCapture(0, cv.CAP_DSHOW)
        if not self.cam.isOpened():
            self.log("-> Erro ao abrir a câmera. Verifique a conexão...")
            self.finalize()
            return
        self.cam.set(3, 1920)
        self.cam.set(4, 1080)

        # Total de plantas para o progresso (exclui B00)
        num_plants = sum(
            1 for idx in selected_indices if self.ID_PLANT[idx] != "B00")
        self.log(
            f"Processando {num_plants} plantas (excluindo B00 do progresso)...")
        self.update_progress(0, 12)  # Total fixo em 12 plantas

        self.send_grbl('$X')
        self.wait_for_idle()
        self.send_grbl('$H')
        self.wait_for_idle()
        self.send_grbl('$')
        self.send_grbl('?')
        self.send_grbl('G1 F14000')

        processed_plants = 0
        for i, plant_idx in enumerate(selected_indices):
            if not self.running:
                break
            self.log(
                "===============================================================")
            self.log(
                f'Planta {i + 1} de {len(selected_indices)} - Deslocando para ' + self.ID_PLANT[plant_idx])
            self.send_grbl(
                f'G1 X{self.POS_X_PLANT[plant_idx]} Y{self.POS_Y_PLANT[plant_idx]}')
            self.wait_for_idle()
            self.get_image(plant_idx, timestamp)
            # Atualiza o progresso apenas para plantas que não são B00
            if self.ID_PLANT[plant_idx] != "B00":
                processed_plants += 1
                self.update_progress(processed_plants, 12)

        self.update_progress(processed_plants, 12)
        self.log("\nConcluído!")

        # Remove B00.jpg, se existir
        b00_path = os.path.join(self.dir_img, f"{timestamp}_B00.jpg")
        if os.path.exists(b00_path):
            self.log(f"-> Arquivo {b00_path} encontrado. Removendo...")
            os.remove(b00_path)
            self.log(f"-> {b00_path} removido com sucesso.")
        else:
            self.log(
                f"-> Nenhum arquivo {timestamp}_B00.jpg encontrado em {self.dir_img}.")

        self.send_grbl('G0 X0 Y0')
        self.wait_for_idle()
        self.finalize()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.configure("Selected.TButton", background="lightgreen")
    style.configure("TButton", background="white")
    app = App(root)
    root.mainloop()

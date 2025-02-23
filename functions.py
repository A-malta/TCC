import cv2 as cv       
from tkinter import ttk, messagebox
import sys
import serial        
import time

def iniciar_camera(camera_id=0, largura=1920, altura=1080):
    print("Iniciando câmera...")
    cam_local = cv.VideoCapture(camera_id)
    if not cam_local.isOpened():
        messagebox.showerror("Erro", "Não foi possível abrir a câmera. Verifique a conexão.")
        sys.exit(1)
    cam_local.set(3, largura)
    cam_local.set(4, altura)
    return cam_local


def iniciar_serial(porta, baudrate):
    print("Iniciando comunicação com GRBL...")
    try:
        grbl_local = serial.Serial(porta, baudrate, timeout=1)
        time.sleep(2)  
        grbl_local.write(b"\r\n\r\n") 
        time.sleep(2)
        grbl_local.flushInput() 
        print("Conectado ao GRBL na porta:", porta)
        return grbl_local
    except serial.SerialException as e:
        messagebox.showerror("Erro", f"Erro ao conectar na porta {porta}: {e}")
        sys.exit(1)


def send_grbl(cmd, grbl, delay=0.1):
    if grbl is None:
        print("GRBL não inicializado!")
        return
    comando = cmd + "\r\n"
    grbl.write(comando.encode())
    time.sleep(delay)
    while grbl.inWaiting() > 0:
        response = grbl.readline().decode().strip()
        print("GRBL:", response)


def capturar_imagem(indice, cam, dir_img, id_plant):
    if cam is None:
        print("Câmera não inicializada!")
        return
    ret, frame = cam.read()
    if not ret:
        print("Erro ao capturar imagem!")
        return
    frame_resized = cv.resize(frame, (640, 360))
    cv.imshow('Imagem Capturada', frame_resized)
    nome_arquivo = os.path.join(dir_img, f"{id_plant[indice]}.jpg")
    cv.imwrite(nome_arquivo, frame)
    cv.waitKey(30)
    print(f"Imagem da planta {id_plant[indice]} salva em {nome_arquivo}")

def processar_planta(indice, grbl, velocidade, pos_x_plant, pos_y_plant, dir_img, id_plant,move_delay):
    try:
        # Define a velocidade de deslocamento
        cmd_vel = f'G1 F{velocidade}'
        print("Configurando velocidade:", cmd_vel)
        send_grbl(cmd_vel,grbl)
        
        # Comando de movimentação para a planta selecionada
        cmd_move = f"G1 X{pos_x_plant[indice]} Y{pos_y_plant[indice]}"
        print("Movendo para:", cmd_move)
        send_grbl(cmd_move,grbl)
        
        # Aguarda o tempo de deslocamento
        time.sleep(move_delay)
        
        # Captura a imagem
        capturar_imagem(indice, cam, dir_img, id_plant)
        
        # Opcional: Retorna para a posição inicial (X0 Y0)
        print("Retornando para a posição inicial (X0 Y0)...")
        send_grbl('G0 X0 Y0',grbl)
        time.sleep(move_delay)
        messagebox.showinfo("Concluído", f"Processo da planta {id_plant[indice]} concluído!")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro durante o processo da planta {id_plant[indice]}: {e}")

def executar_planta(indice, grbl, speed_entry, pos_x_plant, pos_y_plant, dir_img, id_plant, move_delay):
    try:
        velocidade = int(speed_entry.get())
    except ValueError:
        messagebox.showerror("Erro", "Velocidade inválida. Por favor, insira um número inteiro.")
        return
    thread = threading.Thread(target=processar_planta, args=(indice, grbl, velocidade, pos_x_plant, pos_y_plant, dir_img, id_plant, move_delay))
    thread.start()

def init_system(dir_img, id_plant, port, baudrate):
    cam = iniciar_camera()
    grbl = iniciar_serial(port, baudrate)
    # Teste inicial de captura
    capturar_imagem(0, cam, dir_img, id_plant)

def close_system(grbl, cam):
    if grbl is not None:
        grbl.close()
    if cam is not None:
        cam.release()
    cv.destroyAllWindows()
    root.destroy()


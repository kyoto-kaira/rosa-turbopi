import os
import urllib.request

import cv2
import numpy as np
from dotenv import load_dotenv
from ultralytics import YOLOWorld

load_dotenv()
timeout = float(os.getenv("ROSBRIDGE_TIMEOUT_S", "5"))
HOST = os.getenv("ROSBRIDGE_HOST", "localhost")
port = 8080
URL = f"http://{HOST}:{port}/snapshot?topic=/image_raw"

model = YOLOWorld("yolov8s-worldv2.pt")
# model.set_classes(["person", "bottle", "chair", "cup", "laptop"])  # 探したい物

with urllib.request.urlopen(URL, timeout=5) as res:
    data = res.read()
frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

results = model(frame)
results[0].save(filename="result_turbopi.jpg")

for box in results[0].boxes:
    cls_name = model.names[int(box.cls[0])]
    conf = float(box.conf[0])
    x1, y1, x2, y2 = box.xyxy[0].tolist()
    print(f"クラス: {cls_name}, 信頼度: {conf:.2f}, 座標: ({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})")

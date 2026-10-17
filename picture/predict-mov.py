from ultralytics import YOLO

HOST = "192.168.0.33"
URL = (
    f"http://{HOST}:8080/stream?topic=/image_raw"
    "&type=mjpeg&width=640&height=480&quality=60"
)

model = YOLO("yolo26n.pt")

# stream=True: フレームごとにジェネレータで処理（メモリ節約）
results = model(source=URL, show=True, save=True, stream=True)

for r in results:
    for box in r.boxes:
        cls_name = model.names[int(box.cls[0])]
        conf = float(box.conf[0])
        print(f"クラス: {cls_name}, 信頼度: {conf:.2f}")
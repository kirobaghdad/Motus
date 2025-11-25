import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from PIL import Image
import numpy as np
from ultralytics import YOLO

app = FastAPI()

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLOv8n model
model = YOLO("yolov8n.pt")  # path to your YOLOv8 nano weights

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    while True:
        try:
            # Receive JPEG bytes from client
            data = await websocket.receive_bytes()
            image = Image.open(BytesIO(data)).convert("RGB")
            frame = np.array(image)  # H x W x 3, RGB

            # Run YOLOv8 inference
            results = model(frame)
            detected_objects = []

            # Extract detected class labels
            for r in results:
                # r.boxes.cls contains class indices, r.names maps index -> label
                labels = [r.names[int(cls)] for cls in r.boxes.cls]
                detected_objects.extend(labels)

            # Remove duplicates if desired
            detected_objects = list(set(detected_objects))

            # Send list of labels as a UTF-8 encoded string (JSON could also be used)
            await websocket.send_json({"objects": detected_objects})

        except Exception as e:
            print("WebSocket error:", e)
            break

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)

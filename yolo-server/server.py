import uvicorn
import json
import os
import numpy as np
import cv2
from fastapi import FastAPI, WebSocket
from ultralytics import YOLO
from datetime import datetime

app = FastAPI()

# Load YOLOv8n model
model = YOLO("yolov8n.pt")

# Create folder to save frames
save_dir = "reconstructed_frames"
os.makedirs(save_dir, exist_ok=True)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    frame_count = 0

    while True:
        # Receive JSON message
        data = await websocket.receive_text()
        message = json.loads(data)

        width = message["width"]
        height = message["height"]
        bytesPerRow = message["bytesPerRow"]
        # The client sends the bytes as a hex string.
        byte_string = bytes.fromhex(message["bytes"])
        

        # Reconstruct BGRA8888 frame from buffer
        bgra_frame = np.lib.stride_tricks.as_strided(
            np.frombuffer(byte_string, dtype=np.uint8),
            shape=(height, width, 4),
            strides=(bytesPerRow, 4, 1)
        )

        # Convert BGRA to RGB
        try:
            rgb_frame = cv2.cvtColor(bgra_frame, cv2.COLOR_BGRA2RGB)
            if rgb_frame is None or rgb_frame.size == 0:
                print("Error: Frame conversion to RGB failed.")
                continue
        except cv2.error as e:
            print(f"OpenCV error during color conversion: {e}")
            continue

        # Save reconstructed frame
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        save_path = os.path.join(save_dir, f"frame_{timestamp}.jpg")
        cv2.imwrite(save_path, cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR))  # save as BGR for OpenCV

        # Run YOLO detection
        results = model(rgb_frame)
        labels_list = []
       
        # `results[0].boxes` is a Boxes object
        for box in results[0].boxes:
            label_index = int(box.cls)       # .cls is already a scalar (tensor-like)
            confidence = float(box.conf)     # .conf is already a scalar
            label_name = model.names[label_index]
            labels_list.append({"label": label_name, "confidence": confidence})

        # Send JSON back
        await websocket.send_text(json.dumps({"detections": labels_list}))
        
        frame_count += 1
        print(f"Processed and saved frame #{frame_count}: {save_path}")

    # cv2.destroyAllWindows()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

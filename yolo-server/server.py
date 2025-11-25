import uvicorn
import numpy as np
import cv2
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from PIL import Image

app = FastAPI()

# Allow all origins (or restrict to your phone IP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dummy detection function
def detect_objects(frame: np.ndarray):
    # Example: convert to gray and draw a dummy rectangle
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(frame, (50,50), (200,200), (0,255,0), 2)
    return frame

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_bytes()  # Receive JPEG bytes
        image = Image.open(BytesIO(data))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Run detection
        output_frame = detect_objects(frame)

        # Send back result as JPEG
        _, jpeg = cv2.imencode(".jpg", output_frame)
        await websocket.send_bytes(jpeg.tobytes())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

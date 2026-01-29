import cv2
import time
import asyncio
import json
import numpy as np
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription

# It is recommended to run the server first before running this script.
# Make sure to install the required libraries: pip install opencv-python numpy aiohttp aiortc

class Signaling:
    def __init__(self, server_url):
        self.server_url = server_url
        self.session = aiohttp.ClientSession()

    async def connect(self):
        pass

    async def send(self, desc):
        url = f"{self.server_url}/offer"
        data = {"sdp": desc.sdp, "type": desc.type}
        async with self.session.post(url, json=data) as response:
            if response.status != 200:
                print(f"Error sending offer: {response.status}")

    async def receive(self):
        url = f"{self.server_url}/ws"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return RTCSessionDescription(sdp=data["sdp"], type=data["type"])
            else:
                print(f"Error receiving answer: {response.status}")
                await asyncio.sleep(1)
        return None

    async def close(self):
        await self.session.close()

async def run():
    """
    Captures webcam stream, sends frames to a YOLO server for object detection,
    and displays the annotated video stream with performance metrics.
    """
    # Placeholder for the signaling server URL
    signaling = Signaling("http://172.28.121.105:8080")
    pc = RTCPeerConnection()
    
    # Create a data channel to send frames and receive detections
    data_channel = pc.createDataChannel("frames")
    
    # Global variable to store the latest detections
    latest_detections = []

    try:
        print("Connecting to signaling server...")
        await signaling.connect()
        print("Connected to signaling server.")

        @data_channel.on("open")
        def on_open():
            print("Data channel is open.")

        @data_channel.on("message")
        async def on_message(message):
            nonlocal latest_detections
            response_data = json.loads(message)
            latest_detections = response_data.get("detections", [])


        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam.")
            return

        frame_count = 0
        total_latency = 0
        start_time = time.time()

        # Set a font for displaying text on the frame
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Negotiate the connection
        await pc.setLocalDescription(await pc.createOffer())
        await signaling.send(pc.localDescription)

        # Wait for the answer
        while True:
            answer = await signaling.receive()
            if answer:
                await pc.setRemoteDescription(answer)
                break
        
        # We need to wait for the data channel to be open
        while data_channel.readyState != "open":
            await asyncio.sleep(0.1)


        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame.")
                break

            request_start_time = time.time()

            # Convert frame to BGRA, which is what the server expects
            bgra_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            
            height, width, _ = bgra_frame.shape
            bytes_per_row = bgra_frame.strides[0]

            # Prepare the message for the server
            message = {
                "width": width,
                "height": height,
                "bytesPerRow": bytes_per_row,
                # Convert bytes to a list of ints for JSON serialization, as expected by the server
                "bytes": bgra_frame.tobytes().hex()
            }
            
            # Send frame data as a JSON string over the data channel
            data_channel.send(json.dumps(message))

            request_end_time = time.time()
            
            # --- Performance Calculation ---
            latency = request_end_time - request_start_time
            total_latency += latency
            frame_count += 1
            
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            avg_latency = total_latency / frame_count if frame_count > 0 else 0
            
            # Calculate FPS based on the time elapsed since the start
            # This provides a more stable FPS count over time
            avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0

            # --- Display Annotations and Metrics ---
            detections = latest_detections

            for detection in detections:
                 label = detection.get("label")
                 confidence = detection.get("confidence")
                 # Note: Bounding box coordinates are needed from the server to draw them.
                 # Example assuming server sends 'box': [x1, y1, x2, y2]
                 box = detection.get("box") 
                 if box:
                     cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
                     cv2.putText(frame, f"{label}: {confidence:.2f}", (box[0], box[1] - 10), 
                                 font, 0.5, (0, 255, 0), 2)
            
            # Display the performance metrics on the frame
            cv2.putText(frame, f"Avg FPS: {avg_fps:.2f}", (10, 30), font, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Avg Latency: {avg_latency*1000:.2f} ms", (10, 60), font, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Detections: {len(detections)}", (10, 90), font, 0.7, (255, 255, 255), 2)


            # Show the frame
            cv2.imshow("Webcam YOLO Stream", frame)

            # Exit loop if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Clean up
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        print("Stream ended. Webcam released and windows closed.")
        if 'pc' in locals() and pc.connectionState != 'closed':
            await pc.close()
        if 'signaling' in locals():
            await signaling.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrupted by user.")

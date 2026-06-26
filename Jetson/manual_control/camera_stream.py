from flask import Flask, Response
import cv2
import time

app = Flask(__name__)


def gstreamer_pipeline(sensor_id=0, width=1280, height=720, fps=30):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"framerate={fps}/1 ! "
        f"nvvidconv ! "
        f"video/x-raw, format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=BGR ! "
        f"appsink drop=true sync=false"
    )


def generate_frames(sensor_id=0):
    cap = cv2.VideoCapture(gstreamer_pipeline(sensor_id), cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print(f"Cannot open camera sensor-id={sensor_id}")
        return

    print(f"Camera sensor-id={sensor_id} opened")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Failed to read frame")
            time.sleep(0.1)
            continue

        # Resize for smoother streaming
        frame = cv2.resize(frame, (640, 360))

        ret, buffer = cv2.imencode(".jpg", frame)

        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return """
    <html>
        <head>
            <title>Jetson Camera Stream</title>
            <style>
                body {
                    background: #111;
                    color: white;
                    text-align: center;
                    font-family: Arial;
                }
                img {
                    width: 90%;
                    max-width: 900px;
                    border-radius: 12px;
                    margin-top: 20px;
                }
                a {
                    color: #00d4ff;
                    font-size: 22px;
                    margin: 20px;
                }
            </style>
        </head>
        <body>
            <h1>Jetson Camera Stream</h1>
            <p>
                <a href="/cam0">Camera 0</a>
                <a href="/cam1">Camera 1</a>
            </p>
            <img src="/video0">
        </body>
    </html>
    """


@app.route("/cam0")
def cam0():
    return """
    <html>
        <body style="background:#111; text-align:center;">
            <h1 style="color:white;">Camera 0</h1>
            <img src="/video0" style="width:90%;">
        </body>
    </html>
    """


@app.route("/cam1")
def cam1():
    return """
    <html>
        <body style="background:#111; text-align:center;">
            <h1 style="color:white;">Camera 1</h1>
            <img src="/video1" style="width:90%;">
        </body>
    </html>
    """


@app.route("/video0")
def video0():
    return Response(
        generate_frames(sensor_id=0),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/video1")
def video1():
    return Response(
        generate_frames(sensor_id=1),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    print("Starting camera stream...")
    print("Open from Windows:")
    print("http://192.168.1.29:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)

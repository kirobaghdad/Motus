import cv2
import time
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0)

while True:
    t0 = time.time()
    ret, frame = cap.read()
    if not ret:
        break
    
    results = model(frame, verbose=False)[0]
    annotated = results.plot()

    latency_ms = (time.time() - t0) * 1000
    cv2.putText(annotated, f"{latency_ms:.1f} ms",
                (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0,255,0), 2)

    cv2.imshow("YOLO Webcam", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

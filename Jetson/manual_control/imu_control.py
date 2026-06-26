from flask import Flask, request, jsonify, render_template_string
import time

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>IMU Terminal Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>

<body style="font-family: Arial; text-align:center; padding:30px;">
    <h1>IMU Terminal Test</h1>

    <button onclick="startIMU()" style="font-size:24px; padding:15px;">
        Start IMU
    </button>

    <p>After pressing Start, check Jetson terminal.</p>

    <script>
        function sendData(alpha, beta, gamma) {
            fetch("/imu", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    alpha: alpha,
                    beta: beta,
                    gamma: gamma
                })
            });
        }

        function handleOrientation(event) {
            sendData(event.alpha, event.beta, event.gamma);
        }

        async function startIMU() {
            if (typeof DeviceOrientationEvent !== "undefined" &&
                typeof DeviceOrientationEvent.requestPermission === "function") {
                const permission = await DeviceOrientationEvent.requestPermission();
                if (permission !== "granted") {
                    alert("IMU permission denied");
                    return;
                }
            }

            window.addEventListener("deviceorientationabsolute", handleOrientation, true);
            window.addEventListener("deviceorientation", handleOrientation, true);

            alert("IMU started. Watch Jetson terminal.");
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/imu", methods=["POST"])
def imu():
    data = request.get_json()

    alpha = data.get("alpha")
    beta = data.get("beta")
    gamma = data.get("gamma")

    print(
        f"Alpha/Yaw: {alpha} | "
        f"Beta/Tilt: {beta} | "
        f"Gamma/Tilt: {gamma}",
        flush=True
    )

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    print("Open this from phone:")
    print("http://192.168.1.29:5055")
    app.run(host="0.0.0.0", port=5055, threaded=True)
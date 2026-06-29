import time
import atexit
import threading
import math
import json
import os

from flask import Flask, request, jsonify, render_template_string
import Jetson.GPIO as GPIO
from adafruit_servokit import ServoKit


# ==================================================
# GPIO CLEAN START
# ==================================================

GPIO.setwarnings(False)

try:
    GPIO.cleanup()
except Exception:
    pass

GPIO.setmode(GPIO.BOARD)
print("GPIO mode set to BOARD")


# ==================================================
# PIN SETTINGS
# ==================================================

MOTOR_PWM_PIN = 33
MOTOR_DIR_PIN = 29

ENC_A = 11  # Yellow wire
ENC_B = 13  # Green wire

SERVO_CHANNEL = 0

MAX_SPEED = 99
WATCHDOG_SECONDS = 1.5

# Servo config file
CONFIG_FILE = "/home/motus/data/motus/car_settings.json"
DEFAULT_SERVO_CENTER_ANGLE = 72
DEFAULT_SERVO_TURN_RANGE = 40


def load_car_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)

            return {
                "servo_center_angle": float(
                    data.get("servo_center_angle", DEFAULT_SERVO_CENTER_ANGLE)
                ),
                "servo_turn_range": float(
                    data.get("servo_turn_range", DEFAULT_SERVO_TURN_RANGE)
                )
            }
        except Exception as e:
            print("Could not load car settings:", e)

    return {
        "servo_center_angle": DEFAULT_SERVO_CENTER_ANGLE,
        "servo_turn_range": DEFAULT_SERVO_TURN_RANGE
    }


def save_car_settings(servo_center_angle, servo_turn_range):
    data = {
        "servo_center_angle": servo_center_angle,
        "servo_turn_range": servo_turn_range
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


loaded_settings = load_car_settings()

SERVO_CENTER_ANGLE = loaded_settings["servo_center_angle"]
SERVO_TURN_RANGE = loaded_settings["servo_turn_range"]

# Motor ramp settings
# 5 every 0.05s means 0 -> 100 takes about 1 second.
MOTOR_RAMP_STEP = 5
MOTOR_RAMP_INTERVAL = 0.05

WHEEL_DIAMETER_M = 0.065
TICKS_PER_WHEEL_REV = 180


# ==================================================
# ENCODER
# ==================================================

class Encoder:
    def __init__(self, pin_a, pin_b, ticks_per_rev, wheel_diameter_m):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.ticks_per_rev = ticks_per_rev
        self.wheel_diameter_m = wheel_diameter_m

        self.ticks = 0
        self.direction = 1

        self.last_speed_ticks = 0
        self.last_speed_time = time.time()

        self.speed_mps = 0.0
        self.rpm = 0.0

        self.lock = threading.Lock()

        GPIO.setup(self.pin_a, GPIO.IN)
        GPIO.setup(self.pin_b, GPIO.IN)

        # Count A rising edge only.
        # Direction comes from motor command.
        GPIO.add_event_detect(self.pin_a, GPIO.RISING, callback=self._update)

        print("Encoder ready on pins 11 and 13")

    def set_direction(self, direction):
        with self.lock:
            if direction > 0:
                self.direction = 1
            elif direction < 0:
                self.direction = -1

    def _update(self, channel):
        with self.lock:
            self.ticks += self.direction

    def ticks_to_distance(self, ticks):
        wheel_circumference = math.pi * self.wheel_diameter_m
        return (ticks / self.ticks_per_rev) * wheel_circumference

    def update_speed(self):
        now = time.time()
        dt = now - self.last_speed_time

        if dt <= 0:
            return

        with self.lock:
            current_ticks = self.ticks

        delta_ticks = current_ticks - self.last_speed_ticks
        delta_distance = self.ticks_to_distance(delta_ticks)

        self.speed_mps = delta_distance / dt

        revs = delta_ticks / self.ticks_per_rev
        self.rpm = (revs / dt) * 60.0

        self.last_speed_ticks = current_ticks
        self.last_speed_time = now

    def get_data(self):
        self.update_speed()

        with self.lock:
            ticks = self.ticks

        distance_m = self.ticks_to_distance(ticks)

        return {
            "ticks": ticks,
            "distance_m": round(distance_m, 3),
            "speed_mps": round(self.speed_mps, 3),
            "rpm": round(abs(self.rpm), 1)
        }

    def reset(self):
        with self.lock:
            self.ticks = 0

        self.last_speed_ticks = 0
        self.last_speed_time = time.time()
        self.speed_mps = 0.0
        self.rpm = 0.0


# ==================================================
# MOTOR DRIVER
# ==================================================

class MotorDriver:
    def __init__(
        self,
        pwm_pin,
        dir_pin,
        frequency=1000,
        ramp_step=MOTOR_RAMP_STEP,
        ramp_interval=MOTOR_RAMP_INTERVAL
    ):
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.frequency = frequency

        # Gradual acceleration settings
        self.ramp_step = float(ramp_step)
        self.ramp_interval = float(ramp_interval)

        self.target_speed = 0.0
        self.current_output_speed = 0.0

        self.lock = threading.Lock()
        self.running = True

        GPIO.setup(self.dir_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.pwm_pin, GPIO.OUT, initial=GPIO.LOW)

        self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
        self.pwm.start(0)

        self.ramp_thread = threading.Thread(target=self._ramp_loop, daemon=True)
        self.ramp_thread.start()

        print("Motor ready with gradual speed ramp")
        print("Motor ramp step:", self.ramp_step)
        print("Motor ramp interval:", self.ramp_interval)

    def _apply_output(self, speed):
        speed = max(-100, min(100, float(speed)))

        if speed > 0:
            # Forward
            GPIO.output(self.dir_pin, GPIO.LOW)
            self.pwm.ChangeDutyCycle(abs(speed))

        elif speed < 0:
            # Backward
            GPIO.output(self.dir_pin, GPIO.HIGH)
            self.pwm.ChangeDutyCycle(abs(speed))

        else:
            self.pwm.ChangeDutyCycle(0)
            GPIO.output(self.dir_pin, GPIO.LOW)

    def _ramp_loop(self):
        while self.running:
            with self.lock:
                target = self.target_speed
                current = self.current_output_speed

                if current != 0 and target != 0 and (current > 0) != (target > 0):
                    if current > 0:
                        next_speed = max(0, current - self.ramp_step)
                    else:
                        next_speed = min(0, current + self.ramp_step)

                else:
                    difference = target - current

                    if abs(difference) <= self.ramp_step:
                        next_speed = target
                    elif difference > 0:
                        next_speed = current + self.ramp_step
                    else:
                        next_speed = current - self.ramp_step

                self.current_output_speed = next_speed
                self._apply_output(next_speed)

            time.sleep(self.ramp_interval)

    def set_speed(self, speed):
        speed = max(-100, min(100, float(speed)))

        with self.lock:
            self.target_speed = speed

    def stop(self):
        # Immediate stop for safety
        with self.lock:
            self.target_speed = 0.0
            self.current_output_speed = 0.0
            self._apply_output(0)

    def cleanup(self):
        self.running = False
        self.stop()
        time.sleep(0.1)
        self.pwm.stop()


# ==================================================
# SERVO DRIVER
# ==================================================

class ServoDriver:
    def __init__(self, channels=16, address=0x40, center_angle=72, turn_range=35):
        self.lock = threading.Lock()
        self.kit = ServoKit(channels=channels, address=address)

        for i in range(channels):
            self.kit.servo[i].set_pulse_width_range(500, 2500)

        self.set_config(center_angle=center_angle, turn_range=turn_range)

        print("Servo ready")
        print(f"Left limit:   {self.min_angle}°")
        print(f"Center angle: {self.center_angle}°")
        print(f"Right limit:  {self.max_angle}°")

    def set_config(self, center_angle=None, turn_range=None):
        with self.lock:
            if center_angle is not None:
                self.center_angle = max(0, min(180, float(center_angle)))

            if turn_range is not None:
                self.turn_range = max(0, min(80, float(turn_range)))

            # Keep calculated servo limits inside the safe 0-180 degree range.
            self.min_angle = max(0, self.center_angle - self.turn_range)
            self.max_angle = min(180, self.center_angle + self.turn_range)

    def get_config(self):
        with self.lock:
            return {
                "servo_center_angle": self.center_angle,
                "servo_turn_range": self.turn_range,
                "servo_min_angle": self.min_angle,
                "servo_max_angle": self.max_angle
            }

    def set_steering(self, channel, value):
        value = max(-1.0, min(1.0, float(value)))

        with self.lock:
            angle = self.center_angle + (value * self.turn_range)
            angle = max(self.min_angle, min(self.max_angle, angle))

        self.kit.servo[channel].angle = angle

    def center(self, channel):
        self.set_steering(channel, 0.0)


# ==================================================
# CAR OBJECTS
# ==================================================

motor = MotorDriver(
    pwm_pin=MOTOR_PWM_PIN,
    dir_pin=MOTOR_DIR_PIN
)

servo = ServoDriver(
    center_angle=SERVO_CENTER_ANGLE,
    turn_range=SERVO_TURN_RANGE
)

encoder = Encoder(
    pin_a=ENC_A,
    pin_b=ENC_B,
    ticks_per_rev=TICKS_PER_WHEEL_REV,
    wheel_diameter_m=WHEEL_DIAMETER_M
)


# ==================================================
# GLOBAL STATE
# ==================================================

last_command_time = time.time()

current_speed = 0
current_steering = 0

# Used only after emergency stop
stop_until = 0

hardware_lock = threading.Lock()


# ==================================================
# SAFETY
# ==================================================

def watchdog_loop():
    global current_speed

    while True:
        time.sleep(0.2)

        if time.time() - last_command_time > WATCHDOG_SECONDS:
            if current_speed != 0:
                print("Watchdog stop")

                current_speed = 0

                with hardware_lock:
                    motor.stop()
                    servo.center(SERVO_CHANNEL)


def cleanup():
    print("Stopping car and cleaning up...")

    try:
        with hardware_lock:
            motor.cleanup()
            servo.center(SERVO_CHANNEL)
    except Exception:
        pass

    try:
        GPIO.cleanup()
    except Exception:
        pass


atexit.register(cleanup)
threading.Thread(target=watchdog_loop, daemon=True).start()


# ==================================================
# FLASK APP
# ==================================================

app = Flask(__name__)


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Jetson Car Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {
            font-family: Arial, sans-serif;
            background: #0d0f14;
            color: white;
            margin: 0;
            padding: 18px;
            text-align: center;
        }

        .card {
            background: #171a22;
            border-radius: 20px;
            padding: 18px;
            margin: 14px auto;
            max-width: 430px;
        }

        .readings {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .box {
            background: #252b38;
            padding: 12px;
            border-radius: 14px;
        }

        .label {
            color: #aaa;
            font-size: 14px;
        }

        .value {
            font-size: 22px;
            font-weight: bold;
        }

        input[type=range] {
            width: 90%;
            touch-action: auto;
        }

        #joystick {
            width: 260px;
            height: 260px;
            background: #222837;
            border: 3px solid #444c60;
            border-radius: 50%;
            margin: 20px auto;
            position: relative;
            touch-action: none;
        }

        #knob {
            width: 85px;
            height: 85px;
            background: #2f80ff;
            border-radius: 50%;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
        }

        button {
            width: 280px;
            height: 65px;
            border: none;
            border-radius: 16px;
            color: white;
            font-size: 22px;
            margin: 8px;
            touch-action: manipulation;
        }

        .stop {
            background: #c62828;
            font-weight: bold;
        }

        .reset {
            background: #0055aa;
        }

        .apply {
            background: #2e7d32;
        }

        .message {
            color: #ccc;
            min-height: 22px;
        }
    </style>
</head>

<body>

    <h1>Jetson Car</h1>

    <div class="card">
        <h2>Encoder Readings</h2>

        <div class="readings">
            <div class="box">
                <div class="label">Ticks</div>
                <div class="value" id="ticks">0</div>
            </div>

            <div class="box">
                <div class="label">Distance</div>
                <div class="value"><span id="distance">0</span> m</div>
            </div>

            <div class="box">
                <div class="label">Speed</div>
                <div class="value"><span id="speed_mps">0</span> m/s</div>
            </div>

            <div class="box">
                <div class="label">RPM</div>
                <div class="value" id="rpm">0</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Joystick</h2>

        <div id="joystick">
            <div id="knob"></div>
        </div>

        <p>
            Command Speed: <span id="cmdSpeed">0</span> |
            Steering: <span id="cmdSteering">0.00</span>
        </p>

        <p style="color:#aaa;">
            Speed increases gradually as you move farther up/down from center.
            Left/Right controls steering.
        </p>
    </div>

    <div class="card">
        <h2>Steering Adjustment</h2>

        <div class="label">Servo Center Angle</div>
        <input id="servoCenterSlider" type="range" min="0" max="180" value="72">
        <div class="value"><span id="servoCenterLabel">72</span>°</div>

        <div class="label" style="margin-top:14px;">Max Turn Range</div>
        <input id="servoRangeSlider" type="range" min="0" max="80" value="40">
        <div class="value">±<span id="servoRangeLabel">40</span>°</div>

        <button class="apply" onclick="applyServoConfig()">Apply Steering Settings</button>
        <p class="message" id="servoMessage"></p>

        <p style="color:#aaa;">
            Center adjusts straight wheels. Max Turn Range adjusts how far left/right the servo can turn.
        </p>
    </div>

    <div class="card">
        <button class="stop"
                onpointerdown="stopCar(event)"
                onclick="stopCar(event)">
            STOP
        </button>

        <button class="reset" onclick="resetEncoder()">Reset Encoder</button>
    </div>

    <script>
        const joystick = document.getElementById("joystick");
        const knob = document.getElementById("knob");

        const servoCenterSlider = document.getElementById("servoCenterSlider");
        const servoCenterLabel = document.getElementById("servoCenterLabel");

        const servoRangeSlider = document.getElementById("servoRangeSlider");
        const servoRangeLabel = document.getElementById("servoRangeLabel");

        let joystickActive = false;

        let currentSpeed = 0;
        let currentSteering = 0;

        let controlTimer = null;
        let controlBusy = false;
        let statusBusy = false;
        let emergencyStop = false;

        const DEADZONE = 0.15;
        const MAX_COMMAND_SPEED = 100;

        servoCenterSlider.addEventListener("input", function() {
            servoCenterLabel.innerText = servoCenterSlider.value;
        });

        servoRangeSlider.addEventListener("input", function() {
            servoRangeLabel.innerText = servoRangeSlider.value;
        });

        function sendControl() {
            if (controlBusy || emergencyStop) return;

            controlBusy = true;

            fetch("/control", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    speed: currentSpeed,
                    steering: currentSteering
                })
            })
            .catch(err => console.log("Control error:", err))
            .finally(() => {
                controlBusy = false;
            });
        }

        function startControlLoop() {
            if (controlTimer !== null) return;
            controlTimer = setInterval(sendControl, 120);
        }

        function stopControlLoop() {
            if (controlTimer !== null) {
                clearInterval(controlTimer);
                controlTimer = null;
            }
        }

        function moveJoystick(clientX, clientY) {
            if (emergencyStop) return;

            const rect = joystick.getBoundingClientRect();

            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            let dx = clientX - centerX;
            let dy = clientY - centerY;

            const maxRadius = rect.width / 2 - knob.offsetWidth / 2;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance > maxRadius) {
                dx = dx / distance * maxRadius;
                dy = dy / distance * maxRadius;
            }

            knob.style.transform =
                `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;

            let x = dx / maxRadius;
            let y = dy / maxRadius;

            if (Math.abs(x) < DEADZONE) x = 0;
            if (Math.abs(y) < DEADZONE) y = 0;

            currentSteering = x;

            // Up/down distance from joystick center controls speed.
            // Slight movement = slow, full up/down = full speed.
            let throttle = -y;

            if (Math.abs(throttle) < DEADZONE) {
                throttle = 0;
            }

            currentSpeed = throttle * MAX_COMMAND_SPEED;

            document.getElementById("cmdSpeed").innerText = currentSpeed.toFixed(0);
            document.getElementById("cmdSteering").innerText = currentSteering.toFixed(2);
        }

        function releaseJoystick() {
            joystickActive = false;
            stopControlLoop();

            currentSpeed = 0;
            currentSteering = 0;

            knob.style.transform = "translate(-50%, -50%)";

            document.getElementById("cmdSpeed").innerText = "0";
            document.getElementById("cmdSteering").innerText = "0.00";

            fetch("/normal_stop", {method: "POST", keepalive: true});
        }

        joystick.addEventListener("pointerdown", function(e) {
            emergencyStop = false;
            joystickActive = true;

            joystick.setPointerCapture(e.pointerId);

            moveJoystick(e.clientX, e.clientY);
            sendControl();
            startControlLoop();
        });

        joystick.addEventListener("pointermove", function(e) {
            if (!joystickActive) return;
            moveJoystick(e.clientX, e.clientY);
        });

        joystick.addEventListener("pointerup", releaseJoystick);
        joystick.addEventListener("pointercancel", releaseJoystick);

        function stopCar(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }

            emergencyStop = true;
            joystickActive = false;
            stopControlLoop();

            currentSpeed = 0;
            currentSteering = 0;

            knob.style.transform = "translate(-50%, -50%)";

            document.getElementById("cmdSpeed").innerText = "0";
            document.getElementById("cmdSteering").innerText = "0.00";

            fetch("/emergency_stop", {method: "POST", keepalive: true});
            setTimeout(() => fetch("/emergency_stop", {method: "POST", keepalive: true}), 100);
            setTimeout(() => fetch("/emergency_stop", {method: "POST", keepalive: true}), 250);
        }

        function resetEncoder() {
            fetch("/reset_encoder", {method: "POST"});
        }

        function loadServoConfig() {
            fetch("/servo_config")
                .then(response => response.json())
                .then(data => {
                    servoCenterSlider.value = Number(data.servo_center_angle).toFixed(0);
                    servoRangeSlider.value = Number(data.servo_turn_range).toFixed(0);

                    servoCenterLabel.innerText = servoCenterSlider.value;
                    servoRangeLabel.innerText = servoRangeSlider.value;
                })
                .catch(err => console.log("Servo config load error:", err));
        }

        function applyServoConfig() {
            const centerAngle = Number(servoCenterSlider.value);
            const turnRange = Number(servoRangeSlider.value);

            fetch("/servo_config", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    servo_center_angle: centerAngle,
                    servo_turn_range: turnRange
                })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById("servoMessage").innerText =
                    "Saved: center = " + data.servo_center_angle +
                    "°, range = ±" + data.servo_turn_range + "°";
            })
            .catch(err => {
                document.getElementById("servoMessage").innerText =
                    "Error saving steering settings";
            });
        }

        function updateStatus() {
            if (statusBusy) return;

            statusBusy = true;

            fetch("/status")
                .then(response => response.json())
                .then(data => {
                    document.getElementById("ticks").innerText = data.encoder.ticks;
                    document.getElementById("distance").innerText = data.encoder.distance_m;
                    document.getElementById("speed_mps").innerText = data.encoder.speed_mps;
                    document.getElementById("rpm").innerText = data.encoder.rpm;
                })
                .catch(err => console.log("Status error:", err))
                .finally(() => {
                    statusBusy = false;
                });
        }

        loadServoConfig();
        setInterval(updateStatus, 500);
    </script>

</body>
</html>
"""


# ==================================================
# ROUTES
# ==================================================

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/control", methods=["POST"])
def control():
    global last_command_time, current_speed, current_steering, stop_until

    # Ignore old control commands only after emergency stop
    if time.time() < stop_until:
        with hardware_lock:
            motor.stop()
            servo.center(SERVO_CHANNEL)

        current_speed = 0
        current_steering = 0

        return jsonify({
            "status": "ignored_after_emergency_stop",
            "speed": 0,
            "steering": 0
        })

    data = request.get_json()

    speed = float(data.get("speed", 0))
    steering = float(data.get("steering", 0))

    speed = max(-MAX_SPEED, min(MAX_SPEED, speed))
    steering = max(-1.0, min(1.0, steering))

    current_speed = speed
    current_steering = steering
    last_command_time = time.time()

    if speed > 0:
        encoder.set_direction(1)
    elif speed < 0:
        encoder.set_direction(-1)

    with hardware_lock:
        motor.set_speed(speed)
        servo.set_steering(SERVO_CHANNEL, steering)

    return jsonify({
        "status": "ok",
        "speed": speed,
        "steering": steering
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "speed": current_speed,
        "steering": current_steering,
        "encoder": encoder.get_data(),
        "servo": servo.get_config()
    })


@app.route("/servo_config", methods=["GET", "POST"])
def servo_config_route():
    if request.method == "GET":
        return jsonify(servo.get_config())

    data = request.get_json()

    center_angle = float(
        data.get("servo_center_angle", SERVO_CENTER_ANGLE)
    )

    turn_range = float(
        data.get("servo_turn_range", SERVO_TURN_RANGE)
    )

    center_angle = max(0, min(180, center_angle))
    turn_range = max(0, min(80, turn_range))

    with hardware_lock:
        servo.set_config(center_angle=center_angle, turn_range=turn_range)
        servo.center(SERVO_CHANNEL)

    save_car_settings(center_angle, turn_range)

    return jsonify(servo.get_config())


@app.route("/reset_encoder", methods=["POST"])
def reset_encoder():
    encoder.reset()
    return jsonify({"status": "encoder reset"})


@app.route("/normal_stop", methods=["POST", "GET"])
def normal_stop():
    global current_speed, current_steering, last_command_time

    current_speed = 0
    current_steering = 0
    last_command_time = time.time()

    with hardware_lock:
        motor.stop()
        servo.center(SERVO_CHANNEL)

    return jsonify({"status": "normal_stopped"})


@app.route("/emergency_stop", methods=["POST", "GET"])
def emergency_stop():
    global current_speed, current_steering, last_command_time, stop_until

    current_speed = 0
    current_steering = 0
    last_command_time = time.time()

    # Emergency stop blocks old delayed commands briefly
    stop_until = time.time() + 1.0

    with hardware_lock:
        motor.stop()
        servo.center(SERVO_CHANNEL)

    return jsonify({"status": "emergency_stopped"})


# Keep old /stop route as emergency stop, just in case
@app.route("/stop", methods=["POST", "GET"])
def stop():
    return emergency_stop()


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    print("Starting phone controller...")
    print("Open from your phone:")
    print("http://192.168.1.29:5000")

    app.run(host="0.0.0.0", port=5000, threaded=True)

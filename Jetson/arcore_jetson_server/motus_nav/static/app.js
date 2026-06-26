const mapImage = document.getElementById("mapImage");
const mapWrap = document.getElementById("mapWrap");
const mapStage = document.getElementById("mapStage");
const canvas = document.getElementById("mapCanvas");
const ctx = canvas.getContext("2d");
let appConfig = null;
let latestStatus = null;
let selectedGoal = null;
let clickPose = null;
let manualTimer = null;
let manualBusy = false;
let joystickActive = false;
let currentManualSpeed = 0;
let currentManualSteering = 0;
let configReloading = false;

const MANUAL_DEADZONE = 0.15;

function toast(text) {
    const box = document.getElementById("toast");
    box.textContent = text;
    box.classList.add("show");
    setTimeout(() => box.classList.remove("show"), 2400);
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`);
    return data;
}

function mapToPixel(x, y) {
    const map = appConfig.map;
    return {
        x: (x - map.origin_x_m) / map.resolution_m_per_px,
        y: map.height_px - (y - map.origin_y_m) / map.resolution_m_per_px,
    };
}

function pixelToMap(px, py) {
    const map = appConfig.map;
    return {
        x: map.origin_x_m + px * map.resolution_m_per_px,
        y: map.origin_y_m + (map.height_px - py) * map.resolution_m_per_px,
    };
}

function resizeCanvas() {
    canvas.width = appConfig?.map.width_px || mapImage.naturalWidth;
    canvas.height = appConfig?.map.height_px || mapImage.naturalHeight;
    fitMapStage();
    drawMap();
}

function fitMapStage() {
    if (!appConfig || !mapWrap.clientWidth || !mapWrap.clientHeight) return;
    const mapWidth = appConfig.map.width_px || mapImage.naturalWidth;
    const mapHeight = appConfig.map.height_px || mapImage.naturalHeight;
    if (!mapWidth || !mapHeight) return;

    const scale = Math.min(
        mapWrap.clientWidth / mapWidth,
        mapWrap.clientHeight / mapHeight,
    );
    mapStage.style.width = `${Math.max(1, Math.floor(mapWidth * scale))}px`;
    mapStage.style.height = `${Math.max(1, Math.floor(mapHeight * scale))}px`;
}

function drawMap() {
    if (!appConfig || !canvas.width) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGraph();
    if (latestStatus?.path) drawPath(latestStatus.path);
    if (clickPose) drawInit(clickPose.x, clickPose.y);
    if (latestStatus?.map_pose) drawCar(latestStatus.map_pose);
}

function drawGraph() {
    const graph = appConfig.graph;
    ctx.lineWidth = 5;
    ctx.strokeStyle = "rgba(37, 99, 235, .38)";
    for (const edge of graph.edges) {
        const a = graph.nodes.find(n => n.id === edge.a);
        const b = graph.nodes.find(n => n.id === edge.b);
        const pa = mapToPixel(a.x, a.y);
        const pb = mapToPixel(b.x, b.y);
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.stroke();
    }

    for (const node of graph.nodes) {
        const p = mapToPixel(node.x, node.y);
        ctx.beginPath();
        ctx.fillStyle = node.goal ? "#dc2626" : "#2563eb";
        ctx.arc(p.x, p.y, node.goal ? 12 : 8, 0, Math.PI * 2);
        ctx.fill();
        ctx.font = "bold 15px sans-serif";
        ctx.fillStyle = "#111827";
        ctx.fillText(node.name, p.x + 13, p.y - 10);
    }
}

function drawPath(path) {
    if (path.length < 2) return;
    ctx.lineWidth = 8;
    ctx.strokeStyle = "#16a34a";
    ctx.beginPath();
    path.forEach((point, index) => {
        const p = mapToPixel(point[0], point[1]);
        if (index === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
    });
    ctx.stroke();
}

function drawInit(x, y) {
    const p = mapToPixel(x, y);
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 16, 0, Math.PI * 2);
    ctx.stroke();
}

function drawCar(pose) {
    const p = mapToPixel(pose.x, pose.y);
    // Canvas y grows downward, so map-positive yaw must be negated.
    const angle = -pose.yaw;
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(angle);
    ctx.fillStyle = "#7c3aed";
    ctx.strokeStyle = "white";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(22, 0);
    ctx.lineTo(-15, -13);
    ctx.lineTo(-9, 0);
    ctx.lineTo(-15, 13);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
}

function buildGoals() {
    const goals = appConfig.graph.nodes.filter(node => node.goal);
    const container = document.getElementById("goalButtons");
    container.innerHTML = "";
    goals.forEach(goal => {
        const button = document.createElement("button");
        button.textContent = goal.name;
        button.onclick = async () => {
            try {
                await api("/api/goal", {
                    method: "POST",
                    body: JSON.stringify({goal_id: goal.id}),
                });
                selectedGoal = goal.id;
                [...container.children].forEach(child => child.classList.remove("selected"));
                button.classList.add("selected");
                toast(`Route planned to ${goal.name}`);
            } catch (error) {
                toast(error.message);
            }
        };
        container.appendChild(button);
    });
}

function updatePanel(status) {
    latestStatus = status;
    const phoneOk = status.phone_connected;
    const trackOk = status.tracking;
    document.getElementById("phoneValue").textContent = phoneOk ? "Connected" : "Disconnected";
    document.getElementById("trackingValue").textContent = trackOk ? "TRACKING" : status.tracking_reason;
    document.getElementById("modeValue").textContent = status.mode;
    document.getElementById("messageValue").textContent = status.message;
    document.getElementById("pwmValue").textContent = status.hardware.speed_pwm;
    document.getElementById("steerValue").textContent =
        status.control_debug?.commanded_steering == null ? status.hardware.steering : status.control_debug.commanded_steering;
    document.getElementById("ageValue").textContent = status.pose_age_s == null ? "-" : `${status.pose_age_s.toFixed(2)} s`;
    document.getElementById("poseDistanceValue").textContent =
        status.pose_odometry?.local_distance_m == null ? "-" : `${status.pose_odometry.local_distance_m.toFixed(2)} m`;
    document.getElementById("poseSpeedValue").textContent =
        status.pose_odometry?.pose_speed_mps == null ? "-" : `${status.pose_odometry.pose_speed_mps.toFixed(2)} m/s`;
    document.getElementById("pathErrorValue").textContent =
        status.control_debug?.path_error_m == null ? "-" : `${status.control_debug.path_error_m.toFixed(2)} m`;
    document.getElementById("headingErrorValue").textContent =
        status.control_debug?.heading_error_deg == null ? "-" : `${status.control_debug.heading_error_deg.toFixed(1)}°`;
    document.getElementById("targetXValue").textContent =
        status.control_debug?.target_x == null ? "-" : `${status.control_debug.target_x.toFixed(2)} m`;
    document.getElementById("targetYValue").textContent =
        status.control_debug?.target_y == null ? "-" : `${status.control_debug.target_y.toFixed(2)} m`;
    if (status.power) updatePowerPanel(status.power);

    if (status.local_pose) {
        document.getElementById("localXValue").textContent = `${status.local_pose.x.toFixed(2)} m`;
        document.getElementById("localYValue").textContent = `${status.local_pose.y.toFixed(2)} m`;
    } else {
        document.getElementById("localXValue").textContent = "-";
        document.getElementById("localYValue").textContent = "-";
    }

    if (status.map_pose) {
        document.getElementById("xValue").textContent = `${status.map_pose.x.toFixed(2)} m`;
        document.getElementById("yValue").textContent = `${status.map_pose.y.toFixed(2)} m`;
        document.getElementById("yawValue").textContent = `${status.map_pose.yaw_deg.toFixed(1)}°`;
    } else {
        document.getElementById("xValue").textContent = status.local_pose ? "Set initial pose" : "-";
        document.getElementById("yValue").textContent = status.local_pose ? "Set initial pose" : "-";
        document.getElementById("yawValue").textContent = status.local_pose ? `${status.local_pose.yaw_deg.toFixed(1)}° local` : "-";
    }

    const main = document.getElementById("mainStatus");
    const mapReady = trackOk && Boolean(status.map_pose);
    main.textContent = mapReady ? "Localization ready" : (trackOk ? "Set initial pose to compute map coordinates" : status.tracking_reason);
    main.className = `status ${mapReady ? "good" : "bad"}`;
    drawMap();
}

async function pollStatus() {
    try {
        await refreshConfigIfChanged();
        const status = await api("/api/status");
        updatePanel(status);
    } catch (error) {
        const main = document.getElementById("mainStatus");
        main.textContent = "Jetson server unavailable";
        main.className = "status bad";
    }
}

async function refreshConfigIfChanged() {
    if (!appConfig || configReloading) return;
    configReloading = true;
    try {
        const nextConfig = await api("/api/config");
        if (nextConfig.image_version !== appConfig.image_version) {
            appConfig = nextConfig;
            selectedGoal = null;
            clickPose = null;
            buildGoals();
            mapImage.onload = resizeCanvas;
            mapImage.src = `${appConfig.map.image}?v=${appConfig.image_version || Date.now()}`;
            toast("Map reloaded");
        }
    } finally {
        configReloading = false;
    }
}

canvas.addEventListener("click", event => {
    if (!appConfig) return;
    const rect = canvas.getBoundingClientRect();
    const px = (event.clientX - rect.left) * canvas.width / rect.width;
    const py = (event.clientY - rect.top) * canvas.height / rect.height;
    clickPose = pixelToMap(px, py);
    document.getElementById("initX").value = clickPose.x.toFixed(2);
    document.getElementById("initY").value = clickPose.y.toFixed(2);
    drawMap();
});

document.getElementById("setInit").onclick = async () => {
    try {
        const x = Number(document.getElementById("initX").value);
        const y = Number(document.getElementById("initY").value);
        const yawDeg = Number(document.getElementById("initYaw").value);
        await api("/api/init", {
            method: "POST",
            body: JSON.stringify({x, y, yaw_deg: yawDeg}),
        });
        clickPose = {x, y};
        toast("Initial map pose set. Reset AR origin on the onboard phone now.");
    } catch (error) {
        toast(error.message);
    }
};

document.getElementById("startButton").onclick = async () => {
    try {
        if (!selectedGoal) throw new Error("Choose a destination first");
        await api("/api/start", {method: "POST"});
        toast("Autonomous navigation started");
    } catch (error) {
        toast(error.message);
    }
};

document.getElementById("stopButton").onclick = async () => {
    try {
        resetJoystick();
        await api("/api/stop", {method: "POST"});
        toast("Vehicle stopped");
    } catch (error) {
        toast(error.message);
    }
};

function updatePowerPanel(power) {
    document.getElementById("normalPwmValue").textContent = power.normal_pwm.toFixed(0);
    document.getElementById("turnPwmValue").textContent = power.turn_pwm.toFixed(0);
    document.querySelectorAll("[data-power-mode]").forEach(button => {
        button.classList.toggle("selected", button.dataset.powerMode === power.mode);
    });
}

async function loadPowerConfig() {
    const power = await api("/api/power");
    updatePowerPanel(power);
}

document.querySelectorAll("[data-power-mode]").forEach(button => {
    button.onclick = async () => {
        try {
            const power = await api("/api/power", {
                method: "POST",
                body: JSON.stringify({mode: button.dataset.powerMode}),
            });
            updatePowerPanel(power);
            if (appConfig?.control) {
                appConfig.control.normal_pwm = power.normal_pwm;
                appConfig.control.turn_pwm = power.turn_pwm;
                appConfig.control.power = power;
            }
            toast(`Power mode: ${button.textContent}`);
        } catch (error) {
            toast(error.message);
        }
    };
});

function updateServoLabels() {
    document.getElementById("servoCenterValue").textContent = document.getElementById("servoCenter").value;
    document.getElementById("servoRangeValue").textContent = document.getElementById("servoRange").value;
}

async function loadServoConfig() {
    const config = await api("/api/servo");
    document.getElementById("servoCenter").value = Math.round(config.center_deg);
    document.getElementById("servoRange").value = Math.round(config.range_deg);
    updateServoLabels();
}

document.getElementById("servoCenter").addEventListener("input", updateServoLabels);
document.getElementById("servoRange").addEventListener("input", updateServoLabels);

document.getElementById("saveServo").onclick = async () => {
    try {
        const centerDeg = Number(document.getElementById("servoCenter").value);
        const rangeDeg = Number(document.getElementById("servoRange").value);
        const config = await api("/api/servo", {
            method: "POST",
            body: JSON.stringify({center_deg: centerDeg, range_deg: rangeDeg}),
        });
        document.getElementById("servoCenter").value = Math.round(config.center_deg);
        document.getElementById("servoRange").value = Math.round(config.range_deg);
        updateServoLabels();
        toast("Steering trim saved");
    } catch (error) {
        toast(error.message);
    }
};

function sendManual(speedPwm, steering, force = false) {
    if (manualBusy && !force) return Promise.resolve();
    manualBusy = true;
    return api("/api/manual", {
        method: "POST",
        body: JSON.stringify({speed_pwm: speedPwm, steering}),
    }).catch(error => toast(error.message))
        .finally(() => {
            manualBusy = false;
        });
}

function maxManualPwm() {
    return appConfig?.control?.max_manual_pwm || 99;
}

function updateManualReadout() {
    document.getElementById("cmdSpeed").textContent = currentManualSpeed.toFixed(0);
    document.getElementById("cmdSteering").textContent = currentManualSteering.toFixed(2);
}

function setKnob(dx = 0, dy = 0) {
    document.getElementById("joystickKnob").style.transform =
        `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
}

function updateJoystick(clientX, clientY) {
    const joystick = document.getElementById("joystick");
    const knob = document.getElementById("joystickKnob");
    const rect = joystick.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    let dx = clientX - centerX;
    let dy = clientY - centerY;
    const maxRadius = rect.width / 2 - knob.offsetWidth / 2;
    const distance = Math.hypot(dx, dy);

    if (distance > maxRadius) {
        dx = dx / distance * maxRadius;
        dy = dy / distance * maxRadius;
    }

    setKnob(dx, dy);

    let x = dx / maxRadius;
    let y = dy / maxRadius;

    if (Math.abs(x) < MANUAL_DEADZONE) x = 0;
    if (Math.abs(y) < MANUAL_DEADZONE) y = 0;

    currentManualSteering = x;
    const throttle = Math.abs(y) < MANUAL_DEADZONE ? 0 : -y;
    currentManualSpeed = throttle * maxManualPwm();
    updateManualReadout();
}

function startManualLoop() {
    if (manualTimer) return;
    manualTimer = setInterval(() => {
        sendManual(currentManualSpeed, currentManualSteering);
    }, 120);
}

function stopManualLoop() {
    clearInterval(manualTimer);
    manualTimer = null;
}

function resetJoystick() {
    joystickActive = false;
    stopManualLoop();
    currentManualSpeed = 0;
    currentManualSteering = 0;
    setKnob();
    updateManualReadout();
}

function releaseJoystick() {
    resetJoystick();
    sendManual(0, 0, true);
}

const joystick = document.getElementById("joystick");
joystick.addEventListener("pointerdown", event => {
    event.preventDefault();
    joystickActive = true;
    joystick.setPointerCapture(event.pointerId);
    updateJoystick(event.clientX, event.clientY);
    sendManual(currentManualSpeed, currentManualSteering);
    startManualLoop();
});
joystick.addEventListener("pointermove", event => {
    if (!joystickActive) return;
    event.preventDefault();
    updateJoystick(event.clientX, event.clientY);
});
joystick.addEventListener("pointerup", event => {
    event.preventDefault();
    releaseJoystick();
});
joystick.addEventListener("pointercancel", releaseJoystick);

async function boot() {
    appConfig = await api("/api/config");
    mapImage.onload = resizeCanvas;
    mapImage.src = `${appConfig.map.image}?v=${appConfig.image_version || Date.now()}`;
    buildGoals();
    await loadServoConfig();
    await loadPowerConfig();
    setInterval(pollStatus, 200);
    pollStatus();
}

boot().catch(error => toast(error.message));
window.addEventListener("resize", () => {
    fitMapStage();
    drawMap();
});

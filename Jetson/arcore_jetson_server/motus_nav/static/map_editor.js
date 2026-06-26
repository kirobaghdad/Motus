const canvas = document.getElementById("editorCanvas");
const ctx = canvas.getContext("2d");
const canvasWrap = document.querySelector(".editor-canvas-wrap");
const image = new Image();

let mapConfig = null;
let graph = {nodes: [], edges: []};
let tool = "select";
let selectedNodeId = null;
let selectedEdgeIndex = null;
let connectFromId = null;
let draggingNodeId = null;
let uploadedImageData = null;

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

function nodeById(id) {
    return graph.nodes.find(node => node.id === id);
}

function mapToPixel(x, y) {
    return {
        x: (x - mapConfig.origin_x_m) / mapConfig.resolution_m_per_px,
        y: mapConfig.height_px - (y - mapConfig.origin_y_m) / mapConfig.resolution_m_per_px,
    };
}

function pixelToMap(px, py) {
    return {
        x: mapConfig.origin_x_m + px * mapConfig.resolution_m_per_px,
        y: mapConfig.origin_y_m + (mapConfig.height_px - py) * mapConfig.resolution_m_per_px,
    };
}

function eventPixel(event) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (event.clientX - rect.left) * canvas.width / rect.width,
        y: (event.clientY - rect.top) * canvas.height / rect.height,
    };
}

function edgeExists(a, b) {
    return graph.edges.some(edge =>
        (edge.a === a && edge.b === b) || (!edge.one_way && edge.a === b && edge.b === a)
    );
}

function nearestNode(px, py) {
    let best = null;
    let bestDist = 18;
    for (const node of graph.nodes) {
        const p = mapToPixel(node.x, node.y);
        const dist = Math.hypot(p.x - px, p.y - py);
        if (dist < bestDist) {
            best = node;
            bestDist = dist;
        }
    }
    return best;
}

function pointSegmentDistance(px, py, ax, ay, bx, by) {
    const abx = bx - ax;
    const aby = by - ay;
    const lengthSq = abx * abx + aby * aby;
    if (lengthSq === 0) return Math.hypot(px - ax, py - ay);

    const t = Math.max(0, Math.min(1, ((px - ax) * abx + (py - ay) * aby) / lengthSq));
    const cx = ax + t * abx;
    const cy = ay + t * aby;
    return Math.hypot(px - cx, py - cy);
}

function nearestEdge(px, py) {
    let bestIndex = null;
    let bestDistance = 16;
    graph.edges.forEach((edge, index) => {
        const a = nodeById(edge.a);
        const b = nodeById(edge.b);
        if (!a || !b) return;
        const pa = mapToPixel(a.x, a.y);
        const pb = mapToPixel(b.x, b.y);
        const dist = pointSegmentDistance(px, py, pa.x, pa.y, pb.x, pb.y);
        if (dist < bestDistance) {
            bestIndex = index;
            bestDistance = dist;
        }
    });
    return bestIndex;
}

function nextNodeId() {
    let index = 1;
    while (graph.nodes.some(node => node.id === `w${index}`)) index += 1;
    return `w${index}`;
}

function nextGoalName() {
    const count = graph.nodes.filter(node => node.goal).length;
    return `Destination ${String.fromCharCode(65 + count)}`;
}

function draw() {
    if (!mapConfig || !canvas.width) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (image.complete && image.naturalWidth) {
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    } else {
        ctx.fillStyle = "#f8fafc";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    ctx.lineWidth = 5;
    ctx.strokeStyle = "rgba(22, 163, 74, .65)";
    graph.edges.forEach((edge, index) => {
        const a = nodeById(edge.a);
        const b = nodeById(edge.b);
        if (!a || !b) return;
        const pa = mapToPixel(a.x, a.y);
        const pb = mapToPixel(b.x, b.y);
        ctx.lineWidth = index === selectedEdgeIndex ? 8 : 5;
        ctx.strokeStyle = index === selectedEdgeIndex ? "#f59e0b" : "rgba(22, 163, 74, .65)";
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.stroke();
    });

    for (const node of graph.nodes) {
        const p = mapToPixel(node.x, node.y);
        const selected = node.id === selectedNodeId || node.id === connectFromId;
        ctx.beginPath();
        ctx.fillStyle = node.goal ? "#dc2626" : "#2563eb";
        ctx.strokeStyle = selected ? "#f59e0b" : "white";
        ctx.lineWidth = selected ? 5 : 3;
        ctx.arc(p.x, p.y, node.goal ? 13 : 10, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.font = "bold 15px sans-serif";
        ctx.fillStyle = "#111827";
        ctx.strokeStyle = "white";
        ctx.lineWidth = 4;
        ctx.strokeText(node.name || node.id, p.x + 14, p.y - 10);
        ctx.fillText(node.name || node.id, p.x + 14, p.y - 10);
    }
}

function fitCanvas() {
    if (!mapConfig || !canvasWrap.clientWidth || !canvasWrap.clientHeight) return;
    const scale = Math.min(
        canvasWrap.clientWidth / mapConfig.width_px,
        canvasWrap.clientHeight / mapConfig.height_px,
    );
    canvas.style.width = `${Math.max(1, Math.floor(mapConfig.width_px * scale))}px`;
    canvas.style.height = `${Math.max(1, Math.floor(mapConfig.height_px * scale))}px`;
}

function updateScaleFields() {
    document.getElementById("mapName").value = mapConfig.name || "Motus Map";
    document.getElementById("imageSizeValue").textContent = `${mapConfig.width_px} x ${mapConfig.height_px}`;
    document.getElementById("resolutionValue").textContent = `${mapConfig.resolution_m_per_px.toFixed(4)} m/px`;
    document.getElementById("realWidth").value = (mapConfig.width_px * mapConfig.resolution_m_per_px).toFixed(2);
    document.getElementById("realHeight").value = (mapConfig.height_px * mapConfig.resolution_m_per_px).toFixed(2);
}

function updateCounts() {
    document.getElementById("nodeCountValue").textContent = graph.nodes.length;
    document.getElementById("edgeCountValue").textContent = graph.edges.length;
}

function updateSelectedPanel() {
    const node = nodeById(selectedNodeId);
    const disabled = !node;
    for (const id of ["nodeId", "nodeName", "nodeSpeed", "nodeX", "nodeY", "nodeGoal", "applyNode"]) {
        document.getElementById(id).disabled = disabled;
    }

    if (!node) {
        document.getElementById("selectedNodeValue").textContent = "No node selected";
        document.getElementById("nodeId").value = "";
        document.getElementById("nodeName").value = "";
        document.getElementById("nodeSpeed").value = "";
        document.getElementById("nodeX").value = "";
        document.getElementById("nodeY").value = "";
        document.getElementById("nodeGoal").checked = false;
        return;
    }

    document.getElementById("selectedNodeValue").textContent = `${node.name} at ${node.x.toFixed(2)}, ${node.y.toFixed(2)} m`;
    document.getElementById("nodeId").value = node.id;
    document.getElementById("nodeName").value = node.name;
    document.getElementById("nodeSpeed").value = node.speed_pwm == null ? "" : node.speed_pwm;
    document.getElementById("nodeX").value = node.x.toFixed(2);
    document.getElementById("nodeY").value = node.y.toFixed(2);
    document.getElementById("nodeGoal").checked = Boolean(node.goal);
}

function refreshUi() {
    updateScaleFields();
    updateCounts();
    updateSelectedPanel();
    fitCanvas();
    draw();
}

function setTool(nextTool) {
    tool = nextTool;
    connectFromId = null;
    selectedEdgeIndex = null;
    document.querySelectorAll("[data-tool]").forEach(button => {
        button.classList.toggle("selected", button.dataset.tool === tool);
    });
    document.getElementById("editorHint").textContent = {
        select: "Select and drag nodes. Edit details in the side panel.",
        add: "Click on the map to add a waypoint.",
        connect: "Click two nodes to create a route link.",
        "delete-edge": "Click near a route link to delete that connection.",
        delete: "Click a node to delete it and its route links.",
    }[tool];
    draw();
}

function addNodeAt(px, py) {
    const m = pixelToMap(px, py);
    const id = nextNodeId();
    const node = {
        id,
        name: `Waypoint ${id.replace("w", "")}`,
        x: Number(m.x.toFixed(3)),
        y: Number(m.y.toFixed(3)),
        goal: false,
    };
    graph.nodes.push(node);
    selectedNodeId = node.id;
    refreshUi();
}

function deleteNode(id) {
    graph.nodes = graph.nodes.filter(node => node.id !== id);
    graph.edges = graph.edges.filter(edge => edge.a !== id && edge.b !== id);
    if (selectedNodeId === id) selectedNodeId = null;
    if (connectFromId === id) connectFromId = null;
    refreshUi();
}

function deleteEdge(index) {
    if (index == null || index < 0 || index >= graph.edges.length) return;
    const edge = graph.edges[index];
    graph.edges.splice(index, 1);
    selectedEdgeIndex = null;
    toast(`Deleted link ${edge.a} to ${edge.b}`);
    refreshUi();
}

function connectNodes(a, b) {
    if (a === b) return;
    if (edgeExists(a, b)) {
        toast("Those nodes are already connected");
        return;
    }
    graph.edges.push({a, b});
    refreshUi();
}

function moveNode(id, px, py) {
    const node = nodeById(id);
    if (!node) return;
    const m = pixelToMap(px, py);
    node.x = Number(m.x.toFixed(3));
    node.y = Number(m.y.toFixed(3));
    updateSelectedPanel();
    draw();
}

canvas.addEventListener("pointerdown", event => {
    if (!mapConfig) return;
    const p = eventPixel(event);
    const node = nearestNode(p.x, p.y);

    if (tool === "add") {
        addNodeAt(p.x, p.y);
        return;
    }

    if (tool === "delete") {
        if (node) deleteNode(node.id);
        return;
    }

    if (tool === "delete-edge") {
        const edgeIndex = nearestEdge(p.x, p.y);
        if (edgeIndex == null) {
            toast("Click closer to a connection");
            return;
        }
        deleteEdge(edgeIndex);
        return;
    }

    if (tool === "connect") {
        if (!node) return;
        if (!connectFromId) {
            connectFromId = node.id;
            selectedNodeId = node.id;
            refreshUi();
            return;
        }
        connectNodes(connectFromId, node.id);
        connectFromId = null;
        selectedNodeId = node.id;
        refreshUi();
        return;
    }

    if (node) {
        selectedNodeId = node.id;
        selectedEdgeIndex = null;
        draggingNodeId = node.id;
        canvas.setPointerCapture(event.pointerId);
        refreshUi();
    } else {
        selectedNodeId = null;
        selectedEdgeIndex = nearestEdge(p.x, p.y);
        refreshUi();
    }
});

canvas.addEventListener("pointermove", event => {
    if (!draggingNodeId || tool !== "select") return;
    const p = eventPixel(event);
    moveNode(draggingNodeId, p.x, p.y);
});

function endDrag() {
    draggingNodeId = null;
}

canvas.addEventListener("pointerup", endDrag);
canvas.addEventListener("pointercancel", endDrag);

document.querySelectorAll("[data-tool]").forEach(button => {
    button.onclick = () => setTool(button.dataset.tool);
});

document.getElementById("applyNode").onclick = () => {
    const node = nodeById(selectedNodeId);
    if (!node) return;

    const nextId = document.getElementById("nodeId").value.trim();
    if (!nextId) {
        toast("Node id is required");
        return;
    }
    if (nextId !== node.id && graph.nodes.some(item => item.id === nextId)) {
        toast("Node id already exists");
        return;
    }

    const oldId = node.id;
    node.id = nextId;
    node.name = document.getElementById("nodeName").value.trim() || nextId;
    node.x = Number(document.getElementById("nodeX").value);
    node.y = Number(document.getElementById("nodeY").value);
    node.goal = document.getElementById("nodeGoal").checked;
    const speed = Number(document.getElementById("nodeSpeed").value);
    if (Number.isFinite(speed) && document.getElementById("nodeSpeed").value !== "") {
        node.speed_pwm = speed;
    } else {
        delete node.speed_pwm;
    }
    if (node.goal && (!node.name || node.name.startsWith("Waypoint"))) {
        node.name = nextGoalName();
    }

    for (const edge of graph.edges) {
        if (edge.a === oldId) edge.a = node.id;
        if (edge.b === oldId) edge.b = node.id;
    }
    selectedNodeId = node.id;
    refreshUi();
};

function recalculateResolution() {
    const realWidth = Number(document.getElementById("realWidth").value);
    const realHeight = Number(document.getElementById("realHeight").value);
    if (Number.isFinite(realWidth) && realWidth > 0) {
        mapConfig.resolution_m_per_px = realWidth / mapConfig.width_px;
    } else if (Number.isFinite(realHeight) && realHeight > 0) {
        mapConfig.resolution_m_per_px = realHeight / mapConfig.height_px;
    }
    mapConfig.name = document.getElementById("mapName").value.trim() || "Motus Map";
    updateScaleFields();
    draw();
}

document.getElementById("realWidth").addEventListener("change", recalculateResolution);
document.getElementById("realHeight").addEventListener("change", recalculateResolution);
document.getElementById("mapName").addEventListener("change", recalculateResolution);

document.getElementById("mapUpload").addEventListener("change", event => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
        const uploaded = new Image();
        uploaded.onload = () => {
            const offscreen = document.createElement("canvas");
            offscreen.width = uploaded.naturalWidth;
            offscreen.height = uploaded.naturalHeight;
            offscreen.getContext("2d").drawImage(uploaded, 0, 0);
            uploadedImageData = offscreen.toDataURL("image/png");

            image.src = uploadedImageData;
            mapConfig.width_px = uploaded.naturalWidth;
            mapConfig.height_px = uploaded.naturalHeight;
            mapConfig.image = "/static/map.png";
            mapConfig.origin_x_m = 0;
            mapConfig.origin_y_m = 0;
            canvas.width = mapConfig.width_px;
            canvas.height = mapConfig.height_px;
            fitCanvas();
            recalculateResolution();
            refreshUi();
        };
        uploaded.src = reader.result;
    };
    reader.readAsDataURL(file);
});

document.getElementById("saveMap").onclick = async () => {
    try {
        recalculateResolution();
        const payload = {
            map: mapConfig,
            graph,
            image_data: uploadedImageData,
        };
        const result = await api("/api/map-editor/save", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        uploadedImageData = null;
        mapConfig = result.map;
        graph = result.graph;
        image.src = `${mapConfig.image}?v=${Date.now()}`;
        toast(result.message || "Map saved");
        refreshUi();
    } catch (error) {
        toast(error.message);
    }
};

async function boot() {
    const data = await api("/api/map-editor");
    mapConfig = data.map;
    graph = data.graph;
    image.onload = () => {
        canvas.width = mapConfig.width_px;
        canvas.height = mapConfig.height_px;
        fitCanvas();
        refreshUi();
    };
    image.src = `${mapConfig.image}?v=${data.image_version}`;
    setTool("select");
}

boot().catch(error => toast(error.message));
window.addEventListener("resize", () => {
    fitCanvas();
    draw();
});

const PriorityQueue = require('../utils/priorityQueue');
class HDMap {
  constructor(data = {}) {
    this.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    this.edges = Array.isArray(data.edges) ? data.edges : [];
    const places_arr = Array.isArray(data.places) ? data.places : [];
    this.regions = Array.isArray(data.regions) ? data.regions : [];
    this.block_size = data.block_size_in_foot;
    this.foot = data.foot_in_cm;

    // Map nodeId -> node object for quick lookup
    this.nodeMap = new Map();
    for (const n of this.nodes) {
      if (n && n.id != null) this.nodeMap.set(n.id, n);
    }

    // Map place name -> node object for quick lookup
    this.places = new Map();
    for (const p of places_arr) {
      this.places.set(p.name, p.node_id);
    }

    // Build adjacency lists for every node:
    // { incoming: [...edges], outgoing: [...edges]}
    this.nodeEdges = {};
    for (const n of this.nodes) {
      this.nodeEdges[n.id] = { incoming: [], outgoing: []};
    }

    for (const e of this.edges) {
      const from = e.from;
      const to = e.to;
      const bidirectional = e.bi_directional || false;
      if (from && this.nodeEdges[from]) {
        this.nodeEdges[from].outgoing.push(e);
        if (bidirectional) {
          this.nodeEdges[from].incoming.push(e);
        }
      }
      if (to && this.nodeEdges[to]) {
        this.nodeEdges[to].incoming.push(e);
        if (bidirectional) {
          this.nodeEdges[to].outgoing.push(e);
        }
      }
    }
  }

  getNodes() {
    return this.nodes;
  }

  getEdges() {
    return this.edges;
  }

  getNodeById(id) {
    return this.nodeMap.get(id) || null;
  }

  getIncomingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].incoming) || [];
  }

  getOutgoingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].outgoing) || [];
  }

  // Utility: get neighbor node id for a node
  getNeighbour(id, edge) {
    if (!edge) return null;
    if (edge.to === id) {
      return edge.from;
    } else if (edge.from === id) {
      return edge.to;
    } else {
      return null;
    }
  }

  // get place id
  getPlaceId(name){
    if (!name) return null;
    const nodeId = this.places.get(name);
    if (!nodeId) return null;
    return nodeId;
  }

  getNearestNode(pose){
    if (pose === null || pose === undefined){
      return null;
    }
    const sortedNodes = PriorityQueue();
    for(const node of this.nodes){
      const dx = node.x - pose.x;
      const dy = node.y - pose.y;
      const d = (dx * dx + dy * dy);
      sortedNodes.push(node.id, d);
    }
    while (sortedNodes.size() > 0) {
      const node = sortedNodes.pop();
      const nodeId = node.key;
      const nodeObj = this.getNodeById(nodeId);
      if (Math.sqrt(node.priority) <= nodeObj.r) {
        return nodeId;
      }
      for (const edge of this.getIncomingEdges(nodeId)) {
        const neighborId = this.getNeighbour(nodeId, edge);
        const neighborObj = this.getNodeById(neighborId);
        const dx = (nodeObj.x - neighborObj.x) * (nodeObj.x - pose.x);
        const dy = (nodeObj.y - neighborObj.y) * (nodeObj.y - pose.y);
        const dotProduct = dx + dy;
        if (dotProduct > 0) {
          return nodeId;
        }
      }
    }
    return null;
  }

  pointInRectangle(point, x, y, w, h) {
    return (point.x >= x && point.x <= x + w && point.y >= y && point.y <= y + h);
  }

  findRegion(pose) {
    if (pose === null || pose === undefined){
      return null;
    }
    for (const region of this.regions) {
      for (let i = 0; i < region.area.length; i+=4) {
        const x = region.area[i];
        const y = region.area[i+1];
        const w = region.area[i+2];
        const h = region.area[i+3];
        if (this.pointInRectangle(pose, x, y, w, h)) {
          return { entrance_node_id: region.entrance_node_id , banned: region.banned};
        }
      }
    }
    return null;
  }
}

module.exports = HDMap;
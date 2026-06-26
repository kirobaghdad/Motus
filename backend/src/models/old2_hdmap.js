const PriorityQueue = require('../utils/priorityQueue');
class HDMap {
  constructor(data = {}) {
    this.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    this.edges = Array.isArray(data.edges) ? data.edges : [];
    this.places = Array.isArray(data.places) ? data.places : [];
    this.roads = Array.isArray(data.roads) ? data.roads : []
    this.blockSizeInFoot = data.block_size_in_foot;
    this.foot = data.foot_in_meter;
    this.blockSizeInPixel = data.image_width_in_pixel / data.map_width_in_block;

    // Map nodeId -> node object for quick lookup
    this.nodeMap = new Map();
    for (const n of this.nodes) {
      if (n && n.id != null) this.nodeMap.set(n.id, n);
    }

    // Map place name -> place object for quick lookup
    this.placeMap = new Map();
    for (const p of this.places) {
      this.placeMap.set(p.name, p);
    }

    // Map roadId -> road object for quick lookup
    this.roadMap = new Map();
    for (const r of this.roads) {
      this.roadMap.set(r.id, r);
    }

    // Build adjacency lists for every node:
    // { incoming: [...edges], outgoing: [...edges]}
    this.nodeEdges = {};
    for (const n of this.nodes) {
      this.nodeEdges[n.id] = { incoming: [], outgoing: [] };
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

  getRoadById(id) {
    return this.roadMap.get(id) || null;
  }

  getPlaceByName(name) {
    return this.placeMap.get(name) || null;
  }

  getPlacePosition(name) {
    place = this.placeMap.get(name);
    if (place) {
      return place.entrance_position
    }
    return null;
  }

  getIncomingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].incoming) || [];
  }

  getOutgoingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].outgoing) || [];
  }

  getBlockSizeInFoot() {
    return this.blockSizeInFoot;
  }

  getBlockSizeInPixel() {
    return this.blockSizeInPixel;
  }

  getFoot() {
    return this.foot;
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

  getNearestNode(pose) {
    if (pose === null || pose === undefined) {
      return null;
    }
    // first check if pose is inside any place, if so return place
    const place = this.findPlace(pose);
    if (place) {
      if (place.banned) {
        return null;
      }
      return { place: place };
    }
    const sortedNodes = PriorityQueue();
    for (const node of this.nodes) {
      const dx = node.x - pose.x;
      const dy = node.y - pose.y;
      const d = (dx * dx + dy * dy);
      sortedNodes.push(node.id, d);
    }
    while (sortedNodes.size() > 0) {
      const node = sortedNodes.pop();
      const nodeId = node.key;
      const nodeObj = this.getNodeById(nodeId);
      for (const edge of this.getIncomingEdges(nodeId)) {
        const neighborId = this.getNeighbour(nodeId, edge);
        const neighborObj = this.getNodeById(neighborId);
        const dx = (nodeObj.x - neighborObj.x) * (nodeObj.x - pose.x);
        const dy = (nodeObj.y - neighborObj.y) * (nodeObj.y - pose.y);
        const dotProduct = dx + dy;
        if (dotProduct > 0) {
          return { nodeId: nodeId, edge: edge };
        }
      }
    }
    return null;
  }

  isInSameRoad(node1, node2) {
    for (const r1Id in node1.roadIds) {
      for (const r2Id in node2.roadIds) {
        if (r1Id === r2Id) {
          return true;
        }
      }
    }
    return false;
  }

  rayLine(point, point1, point2) {
    if (point1.y > point2.y) {
      let tmp = point2;
      point2 = point1;
      point1 = tmp;
    }

    if (point.y <= point1.y || point.y > point2.y)
      return false;

    if (point1.x === point2.x)
      return (point.x < point1.x);

    const fraction = (point.y - point1.y) / (point2.y - point1.y);
    const intersect_x = point1.x + fraction * (point2.x - point1.x);
    return (point.x < intersect_x);

  }

  rayCasting(point, polygon) {
    let collision = 0;
    for (let i = 0; i < polygon.length; i++) {
      if (i === (polygon.length - 1)) {
        collision += rayLine(point, polygon[i], polygon[0]);
      } else {
        collision += rayLine(point, polygon[i], polygon[i + 1]);
      }
    }
    return (collision % 2 === 1);
  }

  findPlace(pose) {
    if (pose === null || pose === undefined) {
      return null;
    }
    for (const place of this.places) {
      const polygon = place.polygon
      if (this.rayCasting(pose, polygon))
        return place;
    }
    return null;
  }
}

module.exports = HDMap;
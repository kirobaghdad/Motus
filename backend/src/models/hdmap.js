class HDMap {
  constructor(data = {}) {
    this.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    this.edges = Array.isArray(data.edges) ? data.edges : [];

    // Map nodeId -> node object for quick lookup
    this.nodeMap = new Map();
    for (const n of this.nodes) {
      if (n && n.id != null) this.nodeMap.set(n.id, n);
    }

    // Build adjacency lists for every node:
    // { incoming: [...edges], outgoing: [...edges], all: [...edges] }
    this.nodeEdges = {};
    for (const n of this.nodes) {
      this.nodeEdges[n.id] = { incoming: [], outgoing: [], all: [] };
    }

    for (const e of this.edges) {
      const from = e.from;
      const to = e.to;
      if (from && this.nodeEdges[from]) {
        this.nodeEdges[from].outgoing.push(e);
        this.nodeEdges[from].all.push(e);
      }
      if (to && this.nodeEdges[to]) {
        this.nodeEdges[to].incoming.push(e);
        this.nodeEdges[to].all.push(e);
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

  // Returns all edges
  getNodeEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].all) || [];
  }

  getIncomingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].incoming) || [];
  }

  getOutgoingEdges(id) {
    return (this.nodeEdges[id] && this.nodeEdges[id].outgoing) || [];
  }

  // Add an edge to the map and update adjacency lists
  addEdge(edge) {
    if (!edge || !edge.from || !edge.to) return;
    this.edges.push(edge);
    if (!this.nodeEdges[edge.from]) this.nodeEdges[edge.from] = { incoming: [], outgoing: [], all: [] };
    if (!this.nodeEdges[edge.to]) this.nodeEdges[edge.to] = { incoming: [], outgoing: [], all: [] };
    this.nodeEdges[edge.from].outgoing.push(edge);
    this.nodeEdges[edge.from].all.push(edge);
    this.nodeEdges[edge.to].incoming.push(edge);
    this.nodeEdges[edge.to].all.push(edge);
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
}

module.exports = HDMap;
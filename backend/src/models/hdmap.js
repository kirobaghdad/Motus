class HDMap {
    constructor(data = {}) {
        this.nodes = Array.isArray(data.nodes) ? data.nodes : [];
        this.edges = Array.isArray(data.edges) ? data.edges : [];
        this.places = Array.isArray(data.places) ? data.places : [];
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

        // Map edgeId -> edge object for quick lookup
        this.edgeMap = new Map();
        for (const e of this.edges) {
            this.edgeMap.set(e.id, e);
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
            if (from !== null && from !== undefined && this.nodeEdges[from]) {
                this.nodeEdges[from].outgoing.push(e);
                if (bidirectional) {
                    this.nodeEdges[from].incoming.push(e);
                }
            }
            if (to !== null && to !== undefined && this.nodeEdges[to]) {
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

    getEdgeById(id) {
        return this.edgeMap.get(id) || null;
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

    findRegionInMap(pose) {
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
        // second check if pose is on any node
        const node = this.findNode(pose);
        if (node) {
            return { nodeId: node.id };
        }
        // third check if pose is on any edge
        const edge = this.findEdge(pose);
        if (edge) {
            return { edge: edge };
        }
        return null;
    }

    IsValidDirection(edge, p1, p2) {
        if (edge.bi_directional) {
            return true;
        }
        // check if moving from p1 to p2 valid I assume that moving in roads will increase distance from start node
        // no loops and back so car be closer to start again, there is no other way to determine if direction is valid
        // as some roads are complex and dividing road into segment will make computation more complex also.
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        // if distance is small car can return back this small distance without steering
        if (d < 4)
            return true;
        const startNode = this.getNodeById(edge.from);
        const dx1 = startNode.x - p1.x;
        const dy1 = startNode.y - p1.y;
        const d1 = (dx1 * dx1 + dy1 * dy1);
        const dx2 = startNode.x - p2.x;
        const dy2 = startNode.y - p2.y;
        const d2 = (dx2 * dx2 + dy2 * dy2);
        if (d1 < d2) {
            return true;
        } else {
            return false;
        }
    }

    getNearestNodeInEdge(edge, pose) {
        if (pose === null || pose === undefined || edge === null || edge === undefined) {
            return null;
        }
        const node1 = this.getNodeById(edge.from);
        const node2 = this.getNodeById(edge.to);
        const dx1 = node1.x - pose.x;
        const dy1 = node1.y - pose.y;
        const d1 = (dx1 * dx1 + dy1 * dy1);
        const dx2 = node2.x - pose.x;
        const dy2 = node2.y - pose.y;
        const d2 = (dx2 * dx2 + dy2 * dy2);
        if (d1 < d2) {
            return edge.from;
        } else {
            return edge.to;
        }
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
                collision += this.rayLine(point, polygon[i], polygon[0]);
            } else {
                collision += this.rayLine(point, polygon[i], polygon[i + 1]);
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

    findEdge(pose) {
        if (pose === null || pose === undefined) {
            return null;
        }
        for (const edge of this.edges) {
            const polygon = edge.polygon
            if (this.rayCasting(pose, polygon))
                return edge;
        }
        return null;
    }

    findNode(pose) {
        if (pose === null || pose === undefined) {
            return null;
        }
        for (const node of this.nodes) {
            const polygon = node.polygon
            if (this.rayCasting(pose, polygon))
                return node;
        }
        return null;
    }
}

module.exports = HDMap;
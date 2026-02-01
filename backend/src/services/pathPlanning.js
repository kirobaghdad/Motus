const path = require('path');
const loadMap = require('../utils/hdmapLoader');
const HDMap = require('../models/hdmap');
const PriorityQueue = require('../utils/priorityQueue');

// Load HD map once (from config)
const data = loadMap(path.join(__dirname, '..', 'config', 'hdmap.json'));
const hdmap = new HDMap(data);

// Simple straight-line heuristic using lat/lng (approx Euclidean)
function heuristic(nodeA, nodeB) {
  if (!nodeA || !nodeB) return 0;
  const dx = (nodeA.lat || 0) - (nodeB.lat || 0);
  const dy = (nodeA.lng || 0) - (nodeB.lng || 0);
  return Math.sqrt(dx * dx + dy * dy);
}

// A* search on the HDMap between node ids
// Returns array of nodeIds from start -> goal or null if no path
function aStarSearch(startId, goalId) {
  if (!startId || !goalId) return null;
  const startNode = hdmap.getNodeById(startId);
  const goalNode = hdmap.getNodeById(goalId);
  if (!startNode || !goalNode) return null;

  const frontier = new PriorityQueue();
  frontier.push(startId, 0);

  const cameFrom = new Map();
  const gScore = new Map();
  gScore.set(startId, 0);

  while (!frontier.isEmpty()) {
    const current = frontier.pop();
    if (!current) break;
    const currentId = current.key;

    if (currentId === goalId) {
      // reconstruct path
      const pathArr = [];
      let cur = goalId;
      while (cur) {
        pathArr.push(cur);
        cur = cameFrom.get(cur);
      }
      return pathArr.reverse();
    }

    const neighbors = hdmap.getNeighbors(currentId);
    for (const nbId of neighbors) {
      // find edge length between currentId -> nbId
      const edges = hdmap.getOutgoingEdges(currentId).filter(e => e.to === nbId);
      const travelCost = edges.length ? (edges[0].length || 1) : 1;
      const tentativeG = (gScore.get(currentId) || Infinity) + travelCost;
      if (tentativeG < (gScore.get(nbId) || Infinity)) {
        cameFrom.set(nbId, currentId);
        gScore.set(nbId, tentativeG);
        const f = tentativeG + heuristic(hdmap.getNodeById(nbId), goalNode);
        frontier.push(nbId, f);
      }
    }
  }

  return null; // no path
}

module.exports = { aStarSearch };

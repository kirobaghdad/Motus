const loadMap = require('../utils/hdmapLoader');
const HDMap = require('../models/hdmap');
const PriorityQueue = require('../utils/priorityQueue');

// Load HD map once (from config)
const data = loadMap("../config/hdmap.json");
const hdmap = new HDMap(data);

// Simple straight-line heuristic using lat/lng (approx Euclidean)
function heuristic(nodeA, nodeB) {
  if (!nodeA || !nodeB) return 0;
  const dx = nodeA.lat - nodeB.lat;
  const dy = nodeA.lng - nodeB.lng;
  return Math.sqrt(dx * dx + dy * dy);
}

function distance(pose, node) {
  if (!node || !pose) return 0;
  const dx = node.lat - pose.lat;
  const dy = node.lng - pose.lng;
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
  const exploredset = new Set();
  frontier.push(startId, 0);

  const cameFrom = new Map(); // to reconstruct path
  const gScore = new Map(); // to store cost to reach each node from start
  gScore.set(startId, 0);

  while (!frontier.isEmpty()) {
    const current = frontier.pop();
    exploredset.add(current.key);
    if (!current) break;
    const currentId = current.key;

    if (currentId === goalId) {
      // reconstruct path
      const pathArr = [];
      let cur = goalId;
      while (cur !== undefined && cur !== null) {
        pathArr.push(cur);
        cur = cameFrom.get(cur);
      }
      return pathArr.reverse();
    }
    const edges = hdmap.getNodeEdges(currentId);
    for (const e of edges) {
      const neighbourId = hdmap.getNeighbour(currentId,e);
      if (exploredset.has(neighbourId)) continue;
      const travelcost = e.length + gScore.get(currentId);
      // if g cost of neighbour is greater than current one refuse it
      if (travelcost < (gScore.get(neighbourId) || Infinity)) {
        cameFrom.set(neighbourId, currentId);
        gScore.set(neighbourId, travelcost);
        const f = travelcost + heuristic(hdmap.getNodeById(neighbourId), goalNode);
        frontier.push(neighbourId, f);
      }
    }
  }
  return null; // no path
}

function tripPlanning(start, destination) {
  /*
  // find nearest node to start and destination
  const nodes = hdmap.getNodes();
  let startId = null, goalId = null;
  let ds = Infinity, dg = Infinity;

  for (const n of nodes) {
    const dStart = distance(start, n);
    if (dStart < ds) {
      ds = dStart;
      startId = n.id;
    }
    const dGoal = distance(destination, n);
    if (dGoal < dg) {
      dg = dGoal;
      goalId = n.id;
    }
  }
  */
  //get places ids
  startId = hdmap.getPlaceId(start);
  goalId = hdmap.getPlaceId(destination);
  if (startId === null || goalId === null) return null;
  // use a star search
  const path = aStarSearch(startId, goalId) || [];

  // get poses to send to car
  const poses = [];
  //poses.push(start);
  for (const nodeId of path) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ lat: node.lat, lng: node.lng });
  }
  //poses.push(destination);
  return poses;
}

module.exports = { tripPlanning };

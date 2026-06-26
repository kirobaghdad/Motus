const PriorityQueue = require('../utils/priorityQueue');

const { getCarPose } = require('../globals/carState');
const hdmap = require('../globals/mapState');

// Euclidean distance heuristic for A*
function heuristic(nodeA, nodeB) {
  if (!nodeA || !nodeB) return 0;
  const dx = nodeA.x - nodeB.x;
  const dy = nodeA.y - nodeB.y;
  return Math.sqrt(dx * dx + dy * dy);
}

// A* search on the HDMap between node ids
// Returns array of nodeIds from start -> goal or null if no path
function aStarSearch(startId, goalId) {
  if (!startId || !goalId) return null;
  if (startId === goalId) return [startId];
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
    const edges = hdmap.getOutgoingEdges(currentId);
    for (const e of edges) {
      const neighbourId = hdmap.getNeighbour(currentId, e);
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

function optimizePathStart(path, nearestNodeEdge) {
  if (!nearestNodeEdge || !path || path.length < 2) return;
  const nearestEdge = nearestNodeEdge.edge;
  const nearestNode = nearestNodeEdge.nodeId;
  if (nearestEdge) {
    if (nearestEdge === -1) {
      // nearset node could be skiped and car go directly to next node remove first element of path
      path.shift();
    }
    else {
      neighborNodeID = hdmap.getNeighbour(nearestNode, nearestEdge);
      if (neighborNodeID && path[1] === neighborNodeID) {
        // nearest node could be skiped and car go directly to next node remove first element of path
        path.shift();
      }

    }
  }
}

function optimizePathEnd(path, nearestNodeEdge) {
  if (!nearestNodeEdge || !path || path.length < 2) return;
  const nearestEdge = nearestNodeEdge.edge;
  const nearestNode = nearestNodeEdge.nodeId;
  if (nearestEdge) {
    if (nearestEdge === -1) {
      // nearset node could be skiped and car go directly to destination remove last element of path
      path.pop();
    }
    else {
      neighborNodeID = hdmap.getNeighbour(nearestNode, nearestEdge);
      if (neighborNodeID && path[path.length - 2] === neighborNodeID) {
        // nearest node could be skiped and car go directly to next node remove last element of path
        path.pop();
      }

    }
  }
}

function solveSameEdgeCase(path, startNearestNodeEdge, destNearestNodeEdge) {
  if (!startNearestNodeEdge || !destNearestNodeEdge || !path || path.length < 2) return;
  if (startNearestNodeEdge.edge.to === destNearestNodeEdge.edge.to && startNearestNodeEdge.edge.from === destNearestNodeEdge.edge.from) {
    // same edge but must make sure going directly to destination is in the same direction of edge
    if (edge.bi_directional) {
      path = []; // make car go directly to destination if start and destination are in the same edge and edge is bi directional
      return;
    }
    if (startNearestNodeEdge.nodeId === path[0] && destNearestNodeEdge.nodeId === path[1]) {
      path = []; // make car go directly to destination if start and destination are in the same edge
      return;
    }
  }
}

function solveSameNodeCase(path, startNearestNodeEdge, destNearestNodeEdge) {
  if (!startNearestNodeEdge || !destNearestNodeEdge || !path || path.length > 1) return;
  if (startNearestNodeEdge.nodeId === destNearestNodeEdge.nodeId) {
    path = []; // make car go directly to destination if start and destination are the same node
  }
}

function tripPlanning(start, destination) {
  if (!start || !destination) return null;
  if (start === destination) return null;
  // get car pose and find nearest node
  const carposeInMeter = getCarpose()
  const carpose = convertPoseFromMetersToBlock(carposeInMeter);
  const nearestNodeEdge = hdmap.getNearestNode(carpose);
  if (nearestNodeEdge === null) {
    return null;
  }
  //get places ids
  const startId = hdmap.getPlaceId(start);
  const goalId = hdmap.getPlaceId(destination);
  if (startId === null || goalId === null) return null;
  // use a star search
  const path1 = aStarSearch(nearestNodeEdge.nodeId, startId);
  const path2 = aStarSearch(startId, goalId);
  if (path1 === null || path2 === null) {
    return null;
  }
  // optimize path1 by removing case when car go to nearest node and then astar say that other node in same edge is next node.
  optimizePathStart(path1, nearestNodeEdge);
  // get poses to send to car
  // remove duplicate start node
  path1.pop();
  const poses = [];
  poses.push(carpose);
  for (const nodeId of path1) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  for (const nodeId of path2) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  return poses;
}

function getPath(start, destination) {
  // check if start and destination are valid
  if (!start || !destination) return null;
  if (start.x === destination.x && start.y === destination.y) return null;
  // get car pose and find nearest node
  const carposeInMeter = getCarpose()
  const carpose = convertPoseFromMetersToBlock(carposeInMeter);
  const carNearestNodeEdge = hdmap.getNearestNode(carpose);
  if (carNearestNodeEdge === null) {
    return null;
  }
  // check if start and destination are in regions or near to node
  const startNearestNodeEdge = hdmap.getNearestNode(start);
  const destNearestNodeEdge = hdmap.getNearestNode(destination);
  if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
  // get path from car to start
  const path1 = aStarSearch(carNearestNodeEdge.nodeId, startNearestNodeEdge.nodeId);
  if (path1 === null) return null;
  // get path from start to destination
  const path2 = aStarSearch(startNearestNodeEdge.nodeId, destNearestNodeEdge.nodeId);
  if (path2 === null) return null;
  // optimize path1 by removing case when car go to nearest node and then astar say that other node in same edge is next node.
  solveSameNodeCase(path1, carNearestNodeEdge, startNearestNodeEdge);
  solveSameEdgeCase(path1, carNearestNodeEdge, startNearestNodeEdge);
  optimizePathStart(path1, carNearestNodeEdge);
  optimizePathEnd(path1, startNearestNodeEdge);
  // optimize path2 also
  solveSameNodeCase(path2, startNearestNodeEdge, destNearestNodeEdge);
  solveSameEdgeCase(path2, startNearestNodeEdge, destNearestNodeEdge);
  optimizePathStart(path2, startNearestNodeEdge);
  optimizePathEnd(path2, destNearestNodeEdge);
  // combine paths and return poses
  const poses = [];
  poses.push(carpose);
  for (const nodeId of path1) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  poses.push({ x: start.x, y: start.y });
  for (const nodeId of path2) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  poses.push({ x: destination.x, y: destination.y });
  return poses;
}

function convertPosesTometers(poses) {
  if (!poses || poses.length === 0) return null;
  const convertedPoses = [];
  const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
  for (const pose of poses) {
    convertedPoses.push({ x: pose.x * blockSizeInMeter, y: pose.y * blockSizeInMeter });
  }
  return convertedPoses;
}

function convertPosesToPixels(poses) {
  if (!poses || poses.length === 0) return null;
  const convertedPoses = [];
  const blockSizeInPixel = hdmap.getBlockSizeInPixel();
  for (const pose of poses) {
    convertedPoses.push({ x: pose.x * blockSizeInPixel, y: pose.y * blockSizeInPixel });
  }
  return convertedPoses;
}

function convertPoseFromMetersToPixels(pose) {
  if (!pose) return null;
  const blockSizeInPixel = hdmap.getBlockSizeInPixel();
  const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
  return { x: (pose.x / blockSizeInMeter) * blockSizeInPixel, y: (pose.y / blockSizeInMeter) * blockSizeInPixel };
}

function convertPoseFromMetersToBlock(pose) {
  if (!pose) return null;
  const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
  return { x: (pose.x / blockSizeInMeter), y: (pose.y / blockSizeInMeter) };
}

module.exports = { tripPlanning, getPath, convertPosesTometers, convertPosesToPixels, convertPoseFromMetersToPixels };

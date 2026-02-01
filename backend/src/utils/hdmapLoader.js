// src/utils/hdmapLoader.js
// Lightweight loader + helpers for the HD map (reads config/hdmap.json)

const fs = require('fs');

let _cache = null;

function loadMap(path) {
  if (!_cache) {
    _cache = JSON.parse(fs.readFileSync(path, 'utf8'));
  }
  return _cache;
}

module.exports = loadMap;

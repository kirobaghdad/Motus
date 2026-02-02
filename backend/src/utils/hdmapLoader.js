// src/utils/hdmapLoader.js
// Lightweight loader + helpers for the HD map (reads config/hdmap.json)

const fs = require('fs');
const path = require('path');

let _cache = null;

function loadMap(relPath) {
  // Resolve relative paths relative to this module so callers don't depend on process.cwd()
  const defaultPath = path.join(__dirname, '..', 'config', 'hdmap.json');
  const filePath = relPath ? path.resolve(__dirname, relPath) : defaultPath;

  if (!_cache) {
    try {
      _cache = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (err) {
      throw new Error(`hdmapLoader: failed to read map at ${filePath}: ${err.message}`);
    }
  }
  return _cache;
}

module.exports = loadMap;

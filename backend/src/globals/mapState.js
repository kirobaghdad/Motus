const loadMap = require('../utils/hdmapLoader');
const HDMap = require('../models/hdmap');
// Load HD map once (from config)
const data = loadMap("../config/hdmap.json");
const hdmap = new HDMap(data);

module.exports = hdmap;
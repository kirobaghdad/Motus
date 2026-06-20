const mongoose = require('mongoose');

const mapSchema = new mongoose.Schema({
    id: { type: String, required: true },
    edges:{ type: [{
        id: { type: String, required: true },
        distance: { type: Number, required: true },
        direction: { type: String, required: true },
    }], required: true},
    name: { type: String, required: true}
});

module.exports = mongoose.model('map', mapSchema);
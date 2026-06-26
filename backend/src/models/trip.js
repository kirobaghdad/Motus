const mongoose = require('mongoose');

const tripSchema = new mongoose.Schema({
    username: { type: String, required: true },
    tripDateTime: { type: Date, required: true },
    state: { type: String, required: true },
    startLocation:{ type: String, required: true},
    destination: { type: String, required: true}
});

module.exports = mongoose.model('trip', tripSchema);
const mongoose = require('mongoose');

const tokenSchema = new mongoose.Schema({
    username: { type: String, ref: 'user' },
    token: { type: String, required: true },
    createdAt: { 
        type: Date, 
        default: Date.now, 
        expires: '7d' // This token will vanish automatically after 7 days!
    }
});

module.exports = mongoose.model('token', tokenSchema);
import mongoose from 'mongoose';

// Intercept mongoose.connect to use our memory server instead of whatever's in app.js
// This prevents src/config/db.js from failing if MONGO_URI is missing
const originalConnect = mongoose.connect;
mongoose.connect = async (uri, options) => {
    if (uri && uri.includes('memory')) {
        return originalConnect.apply(mongoose, [uri, options]);
    }
    console.log("Mocking mongoose.connect for URI:", uri);
    return Promise.resolve(mongoose.connection);
};

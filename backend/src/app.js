const express = require('express');
const http = require('http');
const {Server} = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*', // tighten in production
    methods: ['GET','POST']
  }
});

app.use(express.json()); // allow app to read json data
app.use(express.urlencoded({ extended: true }));
// Link the routes with a prefix
const tripRoutes = require('./routes/tripRoutes.js');
app.use('/api/trip', tripRoutes);

// Register socket handlers
require('./sockets/trackingHandlers')(io);

const PORT = 3000;
server.listen(PORT, () => console.log(`Server on port ${PORT}`));
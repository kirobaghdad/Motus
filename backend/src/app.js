require('dotenv').config({ path: __dirname + '/.env' });
const express = require('express');
const connectDB = require('./config/db');
connectDB(); // Connect to the database
const http = require('http');
const {Server} = require('socket.io');
const bodyParser = require('body-parser');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*', // tighten in production
    methods: ['GET','POST']
  }
});

app.use(express.json()); // allow app to read json data
app.use(bodyParser.json());
app.use(express.urlencoded({ extended: true }));
// Link the routes with a prefix
const tripRoutes = require('./routes/tripRoute.js');
const loginRoute = require('./routes/loginRoute.js');
const registerRoute = require('./routes/registerRoute.js');
const placesRoute = require('./routes/placesRoute.js');
const profileRoute = require('./routes/profileRoute.js');
app.use('/', tripRoutes);
app.use('/', loginRoute);
app.use('/', registerRoute);
app.use('/', placesRoute);
app.use('/', profileRoute);

// Make io available to controllers via app
app.set('io', io);

// Register socket handlers
require('./sockets/socketManager.js')(io);
require('./sockets/pathHandler.js')(io);

const PORT = 3000;
server.listen(PORT, () => console.log(`Server on port ${PORT}`));
module.exports = (io) => {

    io.users = new Map();

    io.on("connection", (socket) => {
        console.log("a device connected:", socket.id);

        socket.on("register-user", async (data) => {
            const registerUser = require("./registerUser");
            await registerUser(data, socket, io);
        });

        socket.on("car-position", async (data) => {
            const trackingHandler = require("./trackingHandler");
            await trackingHandler(data, socket, io);
        });

        socket.on("finished-trips", async (data) => {
            const tripHandler = require("./tripHandler");
            await tripHandler(data, socket, io);
        });

        socket.on('disconnect', () => {
            console.log('Device disconnected', socket.id);

            for (const [username, socketId] of io.users.entries()) {
                if (socketId === socket.id) {
                    io.users.delete(username);
                    console.log(`Unregistered user ${username} for socket ${socket.id}`);
                }
            }
        });
    });
};
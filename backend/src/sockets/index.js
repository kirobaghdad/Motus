io.users = new Map();

module.exports = (io) => {
    io.on("connection", (socket) => {
        console.log("a device connected:", socket.id);

        socket.on("register-user", require("./registerUser")(data,socket.id));

        socket.on("car-position", require("./trackingHandlers")(data,io));

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
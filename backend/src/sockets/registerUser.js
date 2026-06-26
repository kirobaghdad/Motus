const userSchema = require("../models/user");
const validator = require("../services/validation");
const car_username = process.env.CAR_USERNAME;
const car_password = process.env.CAR_PASSWORD;

module.exports = async (data, socket, io) => {
    // validation first
    expected_body = {
        username: "string",
        password: "string"
    };
    if (!validator(data, expected_body)) {
        return;
    }
    if (io.users.has(data.username)) {
        return;
    }
    try {
        if (data.username === car_username && data.password === car_password) {
            socket.join("only-car");
            io.users.set(data.username, socket.id);
            return;
        }
        user = await userSchema.findOne({ username: data.username });
        if (!user) {
            console.log("user not exist");
            return;
        }
        if (data.password !== user.password) {
            console.log("password is wrong");
        }
        // make user join room to recieve car position
        socket.join("all-users");
        // make user join room to recieve path
        socket.join(`exact-${data.username}`);
        io.users.set(data.username, socket.id);
    } catch (error) {
        console.error("error in fetching user", error);
    }
};
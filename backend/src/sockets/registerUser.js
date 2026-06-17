const userSchema = require("../models/user"); 
const car_username = process.env.CAR_USERNAME;
const car_password = process.env.CAR_PASSWORD;

module.exports = async (data,socket,io) => {
    if(!data.username || !data.password){
        console.log("missing data, user not added to any room");
        return;
    }
    if(io.users.has(data.username)){
        return;
    }
    try {
        if (data.username === car_username && data.password === CAR_PASSWORD) {
            socket.join("only-car");
            io.users.set(data.username,socket.id);
            return;
        }
        user = await userSchema.findOne({username: data.username});
        if (! user){
            console.log("user not exist");
            return;
        }
        if (data.password !== user.password){
            console.log("password is wrong");
        }
        // make user join room to recieve car position
        socket.join("all-users");
        // make user join room to recieve path
        socket.join(`exact-${data.username}`);
        io.users.set(data.username,socket.id);
    } catch (error) {
        console.error("error in fetching user",error);
    }
};
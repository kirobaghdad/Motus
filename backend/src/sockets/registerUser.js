const userSchema = require("../models/user"); 

module.exports = async (data,socketID) => {
    if(!data.username || !data.password){
        console.log("missing data, user not added to any room");
    } else {
        if(io.users.has(data.username)){
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
        socket.join("car_pose_pixel");
        // make user join room to recieve path
        socket.join(`path_pixel_${data.username}`);
        io.users.set(data.username,socketID);
    }
};
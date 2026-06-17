const {convertPoseFromMetersToPixels} = require("../services/pathPlanning"); 
const {updateCarPose} = require("../globals/carState");
const car_username = process.env.CAR_USERNAME;

module.exports = (data, socket, io) => {

    const carSocketId = io.users.get(car_username);    
    if (carSocketId === socket.id){
        updateCarPose(data.x,data.y)
        pose = {x:data.x ,y: data.y};
        convertedPose = convertPoseFromMetersToPixels(pose);
        io.to("all-users").emit('update-car-position',convertedPose);
    }
};
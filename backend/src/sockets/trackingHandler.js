const { convertPoseFromMetersToPixels } = require("../services/pathPlanning");
const { updateCarPose } = require("../globals/carState");
const validator = require("../services/validation");
const parsePose = require("../utils/parser");
const car_username = process.env.CAR_USERNAME;

module.exports = (data, socket, io) => {

    // validation first
    expected_body = {
        x: "number",
        y: "number"
    };
    if (!validator(data, expected_body)) {
        return;
    }
    parsedData = parsePose(data);
    const carSocketId = io.users.get(car_username);
    if (carSocketId === socket.id) {
        updateCarPose(parsedData.x, parsedData.y)
        pose = { x: parsedData.x, y: parsedData.y };
        convertedPose = convertPoseFromMetersToPixels(pose);
        io.to("all-users").emit('update-car-position', convertedPose);
    }
};
const tripSchema = require("../models/trip");
const { updateCarState } = require("../globals/carState");
const validator = require("../services/validation");
const car_username = process.env.CAR_USERNAME;

module.exports = async (data, socket, io) => {
    // validation first
    expected_body = {
        tripId: "string",
        immediate: "boolean",
        completed: "boolean",
        username: "string"
    };
    if (!validator(data, expected_body)) {
        return;
    }

    const carSocketId = io.users.get(car_username);

    if (socket.id === carSocketId) {
        updateCarState(true);
        io.to(`exact-${data.username}`).emit("trip-status", data);
        if (data.immediate) {
            return;
        }
        try {
            updatedTrip = await tripSchema.findByIdAndUpdate(data.tripId, { state: "past" }, { new: true });
            if (!updatedTrip) {
                console.error(`Trip with ID ${data.tripId} not found for update.`);
            }
        } catch (error) {
            console.error("Error in updating finished trip:", error);
        }
    }
};
const tripSchema = require("../models/trip") 
const {updateCarState} = require("../globals/carState")
const car_username = process.env.CAR_USERNAME;

module.exports = async (data, socket) => {

    const carSocketId = io.users.get(car_username);
    
    if (socket.id === carSocketId){
        updateCarState(true)
        try {
            updatedTrip = await tripSchema.findByIdAndUpdate(data.tripId, {state: "past"}, {new: true});
            if (!updatedTrip) {
                console.error(`Trip with ID ${data.tripId} not found for update.`);
            }
        } catch (error) {
            console.error("Error in updating finished trip:", error);
        }
    }
};
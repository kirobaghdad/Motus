const carState = {
    x: null,
    y: null,
    vacant: true
};

function updateCarPose(x, y) {
    carState.x = x;
    carState.y = y;
}

function updateCarState(state) {
    carState.vacant = state;
}

function getCarPose() {
    if (carState.x === null || carState.y === null) {
        return null;
    }
    return { x: carState.x, y: carState.y };
}

function getCarState() { return carState }

module.exports = { updateCarPose, updateCarState, getCarState, getCarPose };
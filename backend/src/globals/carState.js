const carState = {
    x : 0,
    y : 0,
    vacant : true
};

function updateCarPose(x,y){
    carState.x = x;
    carState.y = y;
}

function updateCarState(state){
    carState.vacant = state;
}

function getCarState(){return carState}

module.exports = {updateCarPose,updateCarState,getCarState};
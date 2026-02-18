const carState = {
    lat : 0,
    lng : 0,
    vacant : true
};

function updateCarPose(lat,lng){
    carState.lat = lat;
    carState.lng = lng;
}

function updateCarState(state){
    carState.vacant = state;
}

function getCarState(){return carState}

module.exports = {updateCarPose,updateCarState,getCarState};
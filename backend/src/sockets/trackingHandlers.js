CARCODE = process.env.CAR_SECRET_CODE;

module.exports = (data,io) => {

    console.log("Car moved:", data);
    
    if (data.code === CARCODE){
        pose = {lat:data.lat ,lng: data.lng};
        io.to("car-position-pixel").emit(pose);
    }
};
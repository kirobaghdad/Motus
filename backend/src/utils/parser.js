function parsePose(pose){
    return {
        x: Number(pose.x),
        y: Number(pose.y)
    }
};

module.exports = {parsePose};
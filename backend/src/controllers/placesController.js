const userSchema = require("../models/user"); 
const hdmap = require('../globals/mapState');

const placesController = {

    getPopularPlaces: async(req,res) => {
        try {
            const user = await userSchema.findOne({username:req.user.username});
            if (!user) {
                return res.status(404).json({message: 'User not found'});
            }
            return res.status(200).json({popularPlaces: user.popularPlaces});
        } catch(err) {
            console.error(err);
            return res.status(500).json({ message: 'Error fetching popular places' });
        }
    },
    getPlaces: (req,res) =>{
        const places = hdmap.getPlaces();
        return res.status(200).json({places: places});
    },
    getMap: (req,res) =>{
        return res.status(200).json({URL: "https://alisamye.github.io/map/map.png"});
    }
};

module.exports = placesController;
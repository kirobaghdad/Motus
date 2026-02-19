const tokenSchema = require("../models/token"); 
const userSchema = require("../models/user"); 
const jwt = require("jsonwebtoken");
const JWT_SECRET = process.env.JWT_SECRET_KEY;

const registerController = async (req,res) => {
    try {
        const {email,password,username} = req.body;
        if (!username || !password || !email){
            return res.status(401).json({message:"some or all data are missing"});
        }
        await userSchema.create({email,password,username});
        const payload = {username,email};
        const token = jwt.sign(payload, JWT_SECRET, {expiresIn: '24h'});
        await tokenSchema.create({
            username: username,
            token: token
        });
        return res.json({username: username, token: token});
        
    } catch(err){
        // Error code 11000 means a unique constraint was violated
        if (err.code === 11000) {
            return res.status(400).json({ 
                message: "Username already exists" 
            });
        }
        res.status(500).json({ message: "Server error" });
    }
};

module.exports = registerController;
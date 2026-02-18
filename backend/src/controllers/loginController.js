const tokenSchema = require("../models/token"); 
const userSchema = require("../models/user"); 
const jwt = require("jsonwebtoken");
const JWT_SECRET = process.env.JWT_SECRET_KEY;

const loginController = {
    loginHandler: async (req,res) => {
        if (!JWT_SECRET) {
            return res.status(500).json({message: 'JWT secret not configured'});
        }
        const {username,password} = req.body;
        if (!username || !password) {
            return res.status(400).json({message: 'Username and password are required'});
        }
        // retrieve all users
        user = await userSchema.findOne({username:username});
        if (!user){
            return res.status(401).json({message: 'wrong username'})
        }
        if (user.password !== password) {
            return res.status(401).json({message: 'wrong password'});
        }
        const payload = {
            username : user.username,
            email : user.email
        };
        const token = jwt.sign(payload, JWT_SECRET, {expiresIn: '24h'});
        await tokenSchema.create({
            username: username,
            token: token
        });
        res.json({username: username, token: token});
    },
    logoutHandler: async (req,res) => {
        try {
            await tokenSchema.findOneAndDelete({username:req.user.username});
            return res.status(201).json({message: "logged out successfully"});
        } catch (err) {
            console.log(err);
            res.status(500).json({ message: "Server error" });
        }
    }

};

module.exports = loginController;
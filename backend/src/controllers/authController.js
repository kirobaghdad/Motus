const user = {id:1,username:'Ali',password:'12345678',role:'owner'}; 
const jwt = require("jsonwebtoken");
const JWT_SECRET = process.env.JWT_SECRET_KEY;

authController = (req,res) => {
    if (!JWT_SECRET) {
        return res.status(500).json({message: 'JWT secret not configured'});
    }
    const {username,password} = req.body;
    if (!username || !password) {
        return res.status(400).json({message: 'Username and password are required'});
    }
    if (user.username !== username || user.password !== password) {
        return res.status(401).json({message: 'Invalid credentials'});
    }
    const payload = {
        id : user.id,
        username : user.username,
        role : user.role
    };
    const token = jwt.sign(payload, JWT_SECRET, {expiresIn: '1h'});
    res.json({message: 'login successful',username: username, token});
};

module.exports = authController;
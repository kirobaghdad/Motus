const jwt = require("jsonwebtoken");
const JWT_SECRET = process.env.JWT_SECRET_KEY;
const authenticateJWT = (req,res,next) => {
   const authHeader = req.headers.authorization;

   if (!authHeader){
    return res.status(401).json({message: 'Authorization header missing'}); 
   }
   const token = authHeader.split(' ')[1];

   if (!token) {
    return res.status(401).json({message: 'Token missing'});
   }

   if (!JWT_SECRET) {
    return res.status(500).json({message: 'JWT secret not configured'});
   }

   try {
    const decoded = jwt.verify(token,JWT_SECRET);
    req.user = decoded;
    next();
   } catch (error) {
    return res.status(403).json({message: 'Invalid or expired token'});
   }
};

module.exports = authenticateJWT;
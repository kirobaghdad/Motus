const tokenSchema = require("../models/token");
const userSchema = require("../models/user");
const validator = require("../services/validation");
const jwt = require("jsonwebtoken");
const JWT_SECRET = process.env.JWT_SECRET_KEY;

const profileController = {
    editProfile: async (req, res) => {
        // validation first
        expected_body = {
            username: "string",
            email: "string"
        };
        if (!validator(req.body, expected_body)) {
            return res.status(400).json({ message: "error in body format" });
        }
        try {
            const { username, email } = req.body;
            if (!username || !email) {
                return res.status(400).json({ message: "data not found" });
            }
            const updatedData = { username, email };
            const updatedUser = await userSchema.findOneAndUpdate(
                { username: req.user.username },
                { $set: updatedData },
                { new: true },
            );
            if (!updatedUser) {
                return res.status(404).json({ message: "User not found" });
            }
            const payload = {
                username: username,
                email: email
            };
            const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });
            updatedToken = await tokenSchema.findOneAndUpdate(
                { username: req.user.username },
                { $set: { token: token, username: username } }
            );
            if (!updatedToken) {
                return res.status(404).json({ message: "User not found" });
            }
            res.status(201).json({ username: username, token: token });
        } catch (err) {
            // Error code 11000 means a unique constraint was violated
            if (err.code === 11000) {
                return res.status(400).json({
                    message: "Username already exists"
                });
            }
            res.status(500).json({ message: "Server error" });
        }

    },
    getProfile: (req, res) => {
        return res.status(200).json({
            email: req.user.email,
            username: req.user.username
        });
    }
};

module.exports = profileController;
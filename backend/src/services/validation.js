module.exports = (object, expected) => {
    // first check it is object
    if (typeof object !== "object" || object === null) {
        return false;
    }
    // second check if parameter exist
    for (const key in expected) {
        if (!(key in object)) {
            return false;
        }
    }
    // finally check types valid
    for (const key in object) {
        if (object[key] === null) {
            return false;
        }
        if ( expected[key] === "number" && typeof object[key] === "string") {
            let num = Number(object[key]);
            if (isNaN(num)) {
                return false;
            }
        }
        if (typeof object[key] !== expected[key]) {
            return false;
        }
    }
    return true
}; 
# This is guide to use backend

# first for car 

1- to connect with server use sockect.io-client package join room "only-car"
2- socket = io(server Link) where server Link = http://localhost:3000 --> localhost may be replaced with IP address or domain name depend on case
3- event to publish your pose is "car-position" {x,y,code} consider lat is x and lng is y
4- event to recieve path of travel is "path" Array of {x,y} in meters poses and start and destination and trip id like mobile
5- event to publish finshed trips is "finished-trips" tripId

# second for mobile app

1- you got live location from socket also 
  I- to connect with server use sockect.io-client package
  II- socket = io(server Link,) where server Link = http://localhost:3000 --> localhost may be replaced with IP address or domain name depend on case
  III- event to get new car pose is "update-car-position" {x,y} pixel position in image (room joined is 'all-users')
  IV- for now path will be on event "path-display" (room joined is 'exact-username')
  V- for canceled trips that has no valid path will be on event "canceled" {tripId}

2- for remaining tasks use http request 

# 1- login
- method : POST 
- route : /login
- req.body : json { username:value, password:value }
- res.body : json { username:value, token:value }
# for all requests except login and register put token in headers.authorization to be authenticated 

# 2- register
- method : POST 
- route : /register
- req.body : json { email:value, username:value, password:value }
- res.body : json { username:value, token:value }

# 3- popular-destination
- method : GET
- route : /popular-destination
- req.body : empty
- res.body : Array of strings

# 4- profile
- method : GET
- route : /profile
- req.body : empty
- res.body : { email:value, username:value }

# 5- logout
- method : GET
- route : /logout
- req.body : empty
- res.body : message

# 6- edit profile
- method : POST
- route : /edit/profile
- req.body : json { username:value, email:value }
- res.body : json { username: new value, token:new one}

# 7- retrieve all trips
- method : GET
- route : /trips
- req.body : empty
- res.body : Array of {id,destination,startLocation,dateTime,state}
# notes state could be past, active,live,deleted
# notes destination and startLocation will be name of places

# 8- book trip
- method : POST
- route : /book-trip
- req.body : json {destination string,startLocation string,tripDateTime}
- res.body : message

# 9- delete trip
- method : DELETE
- route : /delete-trip
- req.body : json {id}
- res.body : message

# 10- map
- method : GET
- route : /map
- req.body : empty
- res.body : {URL} a url to image

# 11- places
- method : GET
- route : /places
- req.body : empty
- res.body : json{ places: Array of strings}

# 12- immediate trip
- method : GET
- route : /immediate-trip
- req.body : json {destination: {x,y}, startLocation{x,y}} in meter
- res.body : json {destination: {x,y}, startLocation{x,y},poses} in pixels






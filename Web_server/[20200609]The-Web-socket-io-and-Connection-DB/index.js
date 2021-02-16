var mysql = require('mysql2');
var config = require('config');
var port = config.get('port');
var mysqlConfig = config.get('mysql');
var io = require('socket.io').listen(port);
// Define the parameter to connect database
var db = mysql.createConnection({
    host: mysqlConfig.host,
    port: mysqlConfig.port,
    user: mysqlConfig.user,
    password: mysqlConfig.password,
    database: mysqlConfig.database
});
//Connect to db
// Log any errors connected to the db
db.connect(function (err) {
    if (err) console.log(err)
})
console.log('app listen port ' + port);
// Define/initialize our global vars
var devices = [];
var isInitDevices = false;
var socketCount = 0
var maxIdUserRequest = 0;
//when someone connects to socket => raise event connection
io.sockets.on('connection', function (socket) {
    socketCount++
    io.sockets.emit('users connected', socketCount)
    socket.on('disconnect', function () {
        socketCount--
        io.sockets.emit('users connected', socketCount)
    })
    socket.on('new note', function (data) {
        // New note added, push to all sockets and insert into db
        notes.push(data)
        io.sockets.emit('new note', data)
        // Use node's db injection format to filter incoming data
        db.query('INSERT INTO notes (note) VALUES (?)', data.note)
    })
    if (!isInitDevices) {
        // Initial app start, run db query
        db.query('select id, lati_north, longti_east, lati_south, longti_west from devices')
            .on('result', function (data) {
                // Push results onto the notes array
                devices.push(data);
            })
            .on('end', function () {
                // Only emit notes after query has been completed
                io.sockets.emit('initial devices', devices);
            })
        isInitDevices = true
    } else {
        // Initial notes already exist, send out
        io.sockets.emit('initial devices', devices)
    }
    socket.on('new user_requests', function (data) {
        try {
            console.log('bandwidth user request ' + data.req_bandwidth);
            //client send the new request => insert to db
            db.query(`insert into user_requests (bandwidth) values(${data.req_bandwidth})`)
                .on('result', function (dx) {
                    console.log('send noti new user request ' + dx.insertId);
                    io.sockets.emit('new user_requests ', dx.insertId);
                })
                .on('end', function (dt) {
                    // Only emit notes after query has been completed
                })
        } catch (error) {
            console.error(error);
        }
    })
    socket.on('new regions', function (data) {
        try {
            console.log('selected regions ' + data.id);
            //inser/update new selected regions to db
            db.query(`insert into regions (id, lati_north, longti_east, lati_south, longti_west)
            select ${data.id},${data.lati_north},${data.longti_east},${data.lati_south},${data.longti_west}
            WHERE NOT EXISTS (Select id From regions WHERE id =${data.id}) LIMIT 1`, null, function (err, results, fields) {
                if (!err) {
                    console.log('insert regions successfull '  + data.id);
                    io.sockets.emit('new regions', data);
                }
                else {
                    console.log(err);
                }
            })

        } catch (error) {
            console.error(error);
        }
    })
    socket.on('new regions_of_request', function (data) {
        try {
            console.log('insert regions_of_request ' + data.usr_request_id);
            db.query(`insert into regions_of_request (usr_request_id, region_id)
             values(${data.usr_request_id},${data.region_id})`,
                function (err, results, fields) {
                    if (!err) {
                        console.log('insert regions_of_request ' + data.usr_request_id);
                    }
                    else {
                        console.error(err);
                    }
                })

        } catch (error) {
            console.error(error);
        }

    })
    socket.on('update regions', function (data) {
        try {
            console.log('mapping regions ' + data.device_id);
            db.query(`update regions set device_id='${data.device_id}' where id=${data.region_id}`, null,
                function (err, results, fields) {
                    if (!err) {
                        console.log(`mapping selected regions ${data.device_id} - ${data.region_id}`);
                    }
                    else {
                        console.error(err);
                    }
                })


        } catch (error) {
            console.error(error);
        }

    })
    var myPythonScriptPath = '/mnt/c/Users/Admin/Desktop/web-socket-io-mysql-master/finding_lst_paths.py';
    const {PythonShell} = require("python-shell");

    // Use python shell
    //var PythonShell = require('python-shell');
    var pyshell = new PythonShell(myPythonScriptPath);

    pyshell.on('message', function (message) {
        // received a message sent from the Python script (a simple "print" statement)
        console.log(message);
    });
})

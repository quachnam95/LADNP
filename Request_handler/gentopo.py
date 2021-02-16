#!/usr/bin/python
import os
import sys
import errno
import threading
import time
import numpy
import itertools
import json 
import socket
import socketio
import MySQLdb
import mysql.connector as db
from mysql.connector import Error

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
#from flask.extend.mysql import MySQL

# template_dir = os.path.abspath('../public/')
app = Flask(__name__, template_folder='public')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

from collections import defaultdict
import heapq
from heapq import *

curr_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(curr_path)

#Configure the parameters for database
def db_connect():
    return db.connect(
        host="localhost",
        user="root",
        password="Nam@1234",
        database="namqh"
    )

conn = db_connect()
conn.autocommit = True
cur = conn.cursor(buffered=True)

def db_select_cols(table):
    query = 'select * from %s' % table
    cols = []
    cur.execute(query)
    # Get columns
    desc = cur.description
    for col in desc:
        cols.append(col[0])
    return cols


def db_insert(table, cols, vals):
    isr_col_str = ''
    isr_val_str = ''
    # print (type(vals).__name__)
    if isinstance(vals, dict):
        for col in cols:
            isr_col_str += col + ','
            isr_val_str += '%(' + col + ')s,'
    elif isinstance(vals, tuple):
        for col in cols:
            isr_col_str += col + ','
            isr_val_str += r'%s,'
    else:
        print ('The format of values is wrong. Please use dict or tuple instead')
        return
    isr_col_str = isr_col_str.rstrip(',')
    isr_val_str = isr_val_str.rstrip(',')
    isr_query = 'insert into ' + table + '(' + isr_col_str + ') \
        values(' + isr_val_str + ')'

    cur.execute(isr_query, vals)
    conn.commit()

#This class describes the location of a router in the network
class Device:
    def __init__(self, id, lati_n, longti_e, lati_s, longti_w):
        self.id = id
        self.lati_n = lati_n
        self.longti_e = longti_e
        self.lati_s = lati_s
        self.longti_w = longti_w

    def show(self):
        print ("Device %s, ne=(%f,%f), sw=(%f,%f)" %\
             (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w))

    #Add the router to the database
    def create_new_db(self):
        columns = [
            'lati_north',
            'longti_east',
            'lati_south',
            'longti_west',
        ]
        values = (
            self.lati_n,
            self.longti_e,
            self.lati_s,
            self.longti_w
        )
        db_insert('devices', columns, values)

#This class describes the selected region on the Webapp
class Region:
    id = 0

    def __init__(self, id, lati_n, longti_e, lati_s, longti_w):
        self.id = id
        self.lati_n = lati_n
        self.longti_e = longti_e
        self.lati_s = lati_s
        self.longti_w = longti_w

    def show(self):
        print ("Region %d, ne=(%f,%f), sw=(%f,%f)" %\
             (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w))

    def is_existed(self):
        cur.execute("select * from regions where id = %s" % (self.id))
        if not cur.fetchone():
            return False
        else:
            return True

    #Add the selected region to the database
    def create_new_db(self):
        cols = ['id', 'lati_north', 'longti_east', 'lati_south', 'longti_west']
        vals = (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w)
        if not self.is_existed():
            db_insert('regions', cols, vals)

    #Finding the router that corresponds to the selected regions
    def find_device(self, lst_all_switches):
        self.show()
        for dev in lst_all_switches:
            print ("Considering...")
            dev.show()
            if (dev.lati_n >= self.lati_n
                and dev.longti_e >= self.longti_e
                and dev.lati_s <= self.lati_s
                and dev.longti_w <= self.longti_w):
                return dev

    #Assign the router that corresponds to the selected regions
    def set_device(self, device_id):
        query = "update regions set device_id = '%s' where id = %s" % (device_id, self.id)
        print (query)
        cur.execute(query)

#This class describe the parameters on request of user.
class Request:
    req_id = 0

    def __init__(self, id):
        self.id = id

    @staticmethod
    def create_new_db():
        ''' Insert new request to db '''
        Request.req_id += 1
        db_insert('user_requests', ['id', ], (Request.req_id,))

    def update_db(self, dict_data):
        if dict_data:
            query = "update user_requests set "
            if 'request_type' in dict_data:
                query += 'request_type = %(request_type)s,'
            if 'topo_id' in dict_data:
                query += 'topo_id = %(topo_id)s,'
            if 'status' in dict_data:
                query += 'status = %(status)s,'
            query = query.rstrip(',')
            query += " where id = " + str(dict_data['id'])
            cur.execute(query, dict_data)
            # print cur.statement

#Insert newregions request to database
class RegionRequest:
    id = 0

    def __init__(self, req_id, region_id):
        self.req_id = req_id
        self.region_id = region_id

    def create_new_db(self):
        RegionRequest.id += 1
        cols = ['id', 'usr_request_id', 'region_id']
        vals = (RegionRequest.id, self.req_id, self.region_id)
        db_insert('regions_of_request', cols, vals)


def get_path_node(path, nodes):
    for node in path:
        if isinstance(node, tuple):
            get_path_node(node, nodes)
        else:
            nodes.append(node)
    return nodes

#Dijkstra to find routing paths between switches
def dijkstra(edges, f, t):
    nodes = []
    g = defaultdict(list)
    for id, l, r, c in edges:
        g[l].append((c, r))

    q, seen = [(0, f, ())], set()
    while q:
        (cost, v1, path) = heappop(q)
        if v1 not in seen:
            seen.add(v1)
            path = (v1, path)
            if v1 == t:
                get_path_node(path, nodes)
                return {'cost': cost, 'path': nodes}

            for c, v2 in g.get(v1, ()):
                if v2 not in seen:
                    heappush(q, (cost + c, v2, path))

    return float("inf")


lst_all_switches = []
lst_all_switches_id = []
lst_selected_switches = []
lst_regions = []
lst_selected_regions = []
lst_region_switch= []
lst_all_links = []


def get_resources():
    cur.execute('select * from devices')
    rows = cur.fetchall()
    for row in rows:
        id = row[0]
        # device = Device(row[0], row[1], row[2], row[3], row[4])
        curr_resource = set(lst_all_switches_id)
        if id not in curr_resource:
            lst_all_switches_id.append(id)
            device = Device(id, row[1], row[2], row[3], row[4])
            lst_all_switches.append(device)
    # print lst_all_devices
    # Get all links
    # lst_subnet_dev = []
    query = "select id, src1, src2, total_bandwidth_mbps from links"
    cur.execute(query)
    for link in cur.fetchall():
        lst_all_links.append((link[0], link[1], link[2], link[3]))
        # print lst_all_links

REQUEST_FILE_DIR = 'requests'
REQUEST_FILE_BAK_DIR = REQUEST_FILE_DIR + '/bak'
request_file_bak_dir = os.path.join(curr_path, REQUEST_FILE_BAK_DIR)
request_file_dir = os.path.join(curr_path, REQUEST_FILE_DIR)


def print_path(list_path):
    str_path = ""
    for item in list_path:
        str_path += item + '<->'
    str_path = str_path.rstrip('<->')
    print (str_path)

def create_dir(path):
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

#handle the request
def process_request(delay):
    global j
    while True:

        lst_selected_switches = []
        lst_selected_regions = []
        lst_pairwsie = []
        time.sleep(delay)
        # Get new request
        query = "select * from user_requests where status = 4"
        cur.execute(query)
        rows = cur.fetchall()
        if not rows:
            print('There is no request from user now')
            return
        # Handle each new request
        for row in rows:
            request = Request(row[0])
            print ('Processing request id: ' + str(request.id))
            # Get list of covered device
            query = 'select b.usr_request_id, a.id, a.device_id ' \
                    'from regions a join regions_of_request b ' \
                    'on a.id = b.region_id where b.usr_request_id = %s' % request.id
            cur.execute(query)
            for item in cur.fetchall():
                tmp_lst = set(lst_selected_regions)
                if item[1] not in tmp_lst:
                    lst_selected_regions.append(item[1])
                tmp_lst = set(lst_selected_switches)
                if item[2] not in tmp_lst:
                    lst_selected_switches.append(item[2])
            print ("List of selected regions:")
            print (lst_selected_regions)
            print ("List of selected switches:")
            print (lst_selected_switches)
            #print "List of swiches pairwise:"
            #request.update_db({'id': request.id, 'status': 4})
            lst_paths = []
            num_of_selected_switches = len(lst_selected_switches)
            #switch_path = numpy.zeros(shape=(num_of_selected_switches, num_of_selected_switches))
            for i in range(0, num_of_selected_switches - 1):
                for j in range(i + 1, num_of_selected_switches):
                    u = lst_selected_switches[i]
                    v = lst_selected_switches[j]
                    lst_paths.extend(dijkstra(lst_all_links, u, v)['path'])
                    print("%s,%s,%s")%(u, v,lst_paths)
                    # resultReturn = "Finding path {%s} <--> {%s}...with result {%s}"%(lst_selected_switches[i], lst_selected_switches[j],lst_paths)
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):
                        print("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z])
                    print("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1])
                    # return resultReturn   
                    lst_paths = []

                    lst_paths.extend(dijkstra(lst_all_links,v, u)['path'])
                    print("%s,%s,%s")%(v, u, lst_paths)
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):
                        print("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z])
                    print("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1])  
                    lst_paths = []


# @socketio.on('web', namespace='/web')
#route to / (link: localhost:<port>)
@app.route('/')
def home():
    return render_template('index.html')
#@app.route('/public2/<path:path>')
#def send_js_path(path):
#    return send_from_directory('public', path)

@app.route('/getParam', methods=['GET', 'POST'])
def getParam():
    parsed1 = request.args.get('param1')
    parsed2 = request.args.get('param2')
    result = "Get result = %s and %s"%(parsed1, parsed2)
    print (result)
    return result

@app.route('/newRegions', methods=['GET', 'POST'])
def newRegions():
    region_id = request.args.get('region_id')
    lati_north = request.args.get('lati_north')
    longti_east = request.args.get('longti_east')
    lati_south = request.args.get('lati_south')
    longti_west = request.args.get('longti_west')
    result = "Get result = %s and %s and %s and %s and %s"%(region_id, lati_north, longti_east, lati_south, longti_west)
    print (result)
    return result

@app.route('/run', methods=['GET', 'POST'])
def runMain():
    print ("Start Main Process")
    print ("Collecting resources...")
    get_resources()
    print ("List of all links")
    print (lst_all_links)
    try:
        threading._start_new_thread(process_request, (5,))
        # output = thread.start_new_thread(process_request, (5,))
        # return render_template('/index.html', output=output)
    except:
       print("Error: Unable to start thread")

    while True:
        pass
    print ("End Main Process")

@app.route('/select')
def get_devices():
    db = MySQLdb.connect("localhost", "root", "Nam@1234", "namqh")
    cursor = db.cursor
    cursor.execute("select id, lati_north, longti_east, lati_south, longti_west from devices")
    data = cursor.fetchall
    print(data)
    

@socketio.on('new_user_requests')
def handle_socket_new_requests(json):
    print("Json = %s")%(json)
    print("req_bandwidth = %s")%(json['req_bandwidth'])
    cur.execute("INSERT INTO user_requests (bandwidth) VALUES (%s)", \
        (json['req_bandwidth'])) 
    socketio.emit('new_user_requests')

@socketio.on('new_regions')
def handle_socket_user_requests(json):
    print("Json = %s")%(json)
    print("last request Id = %s")%(json['id'])
    #print("")
    #cur.execute("INSERT InTO regions ()")
    emit('new_regions')

@socketio.on('new_regions_of_request')
def handle_socket_regions_of_request(json):
    print("Json = %s")%(json)
    print("last request usr_request_id = %s")%(json['usr_request_id'])
    print("last request region_id = %s")%(json['region_id'])
    print("socket event new region_of_request received")
    emit('new_regions_of_request')

@socketio.on('update_regions')
def handle_socket_update_regions(json):
    print("Json = %s")%(json)
    print("last request usr_request_id = %s")%(json['divices_id'])
    print("last request region_id = %s")%(json['objRegions_id'])
    emit('new_regions_of_request')


#port default: 5000 (link: localhost:5000)
if __name__ == '__main__':
    socketio.run(app, debug=True)
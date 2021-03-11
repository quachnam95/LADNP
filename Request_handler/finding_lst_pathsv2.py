#!/usr/bin/python
#!/usr/bin/python
import os
import sys
import errno
import threading
import time
import numpy
import itertools
import mysql.connector as db
from mysql.connector import Error
import constants as const
import mininet_utils

import json
from json import load

# from sshtunnel import SSHTunnelForwarder
from collections import defaultdict
from heapq import *

curr_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(curr_path)

#Configure the parameters for database
def db_connect():
    # return db.connect(DB_SERVER, DB_USER, DB_PASSWORD, DB_SCHEMA)
    #HieuDBDATA
    return db.connect(
       host='localhost',
       user='hieunv',
       password='Hieu@1234',
       database='LocAwareNet'
    )

    #NamDBDATA
    # return db.connect(
    #     host='localhost',
    #     user='namqh',
    #     password='Nam@1234',
    #     database='LocAwareNet'
    # )

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
    isr_query = 'insert into ' + table + '(' + isr_col_str + ') values(' + isr_val_str + ')'

    cur.execute(isr_query, vals)
    conn.commit()

class Device:
    def __init__(self, id, lati_n, longti_e, lati_s, longti_w):
        self.id = id
        self.lati_n = lati_n
        self.longti_e = longti_e
        self.lati_s = lati_s
        self.longti_w = longti_w

    def show(self):
        print ("Device %s, ne=(%f,%f), sw=(%f,%f)" % (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w))

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

class Region:
    id = 0

    def __init__(self, id, lati_n, longti_e, lati_s, longti_w):
        self.id = id
        self.lati_n = lati_n
        self.longti_e = longti_e
        self.lati_s = lati_s
        self.longti_w = longti_w

    def show(self):
        print ("Region %d, ne=(%f,%f), sw=(%f,%f)" % (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w))

    def is_existed(self):
        cur.execute("select * from regions where id = %s" % (self.id))
        if not cur.fetchone():
            return False
        else:
            return True

    def create_new_db(self):
        cols = ['id', 'lati_north', 'longti_east', 'lati_south', 'longti_west']
        vals = (self.id, self.lati_n, self.longti_e, self.lati_s, self.longti_w)
        if not self.is_existed():
            db_insert('regions', cols, vals)

    def set_device(self, device_id):
        query = "update regions set device_id = '%s' where id = %s" % (device_id, self.id)
        print(query)
        cur.execute(query)

class Request:
    req_id = 0

    def __init__(self, id):
        self.id = id

    @staticmethod
    def create_new_db():
        """ Insert new request to db """
        Request.req_id += 1
        db_insert('user_requests', ['id', ], (Request.req_id,))

    @staticmethod
    def update_db(dict_data):
        if dict_data:
            query = "update user_requests set "
            if 'request_type' in dict_data:
                query += 'request_type = %(request_type)s,'
            if 'subnet_id' in dict_data:
                query += 'subnet_id = %(subnet_id)s,'
            if 'status' in dict_data:
                query += 'status = %(status)s,'
            query = query.rstrip(',')
            query += " where id = " + str(dict_data['id'])
            cur.execute(query, dict_data)

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
    """ Trace back shortest path """
    for node in path:
        if isinstance(node, tuple):
            get_path_node(node, nodes)
        else:
            nodes.append(node)

def dijkstra(g, src, dst, metric=0):
    """
    Find shortest path based on metric
    :param links: set of all links
    :param sw1: the shortest path between sw1 and sw2
    :param sw2: the shortest path between sw1 and sw2
    :param d: direction of link d=0: from sw1 to sw2, d=1: from sw2 to sw1
    :param metric: -1: minimum delay, 0: minimum cost, lamda: minimum lamda-based cost
    :return: dictionary
    """
    nodes = []
    q, seen = [(0, 0, src, ())], set()
    sum_delay = 0
    while q:
        if metric == -1:
            (sum_delay, sum_cost, v, path) = heappop(q)
        else:
            (sum_cost, sum_delay, v, path) = heappop(q)
        if v not in seen:
            seen.add(v)
            path = (path, v)

            if v == dst:
                get_path_node(path, nodes)
                if metric == -1:
                    return {'sum_delay': sum_delay, "sum_cost": round(sum_cost,2), 'path': nodes}
                else:
                    return {'sum_cost': round(sum_cost,2), "sum_delay": sum_delay, 'path': nodes}

            # Traversing all neighbors of v
            # print (g.get(v))
            for cost, delay, tmp in g.get(v):
                if tmp not in seen:
                    # if metric > 0, new cost is calculated based on this equation
                    # if sum_cost + cost < sum_cost then push tmp to heap
                    if metric == -1:
                        heappush(q, (sum_delay+delay, sum_cost+cost, tmp, path))
                    else:
                        cost_lamda = cost + (metric*delay)
                        heappush(q, (sum_cost + cost_lamda, sum_delay+delay, tmp, path))

def larac_alg(g_links, sw1, sw2, delay_bound, d=0):
    global src, dst
    if d == 0:
        src = sw1
        dst = sw2
    else:
        src = sw2
        dst = sw1
    global path_c, path_d, cost_path_c, cost_path_d, delay_path_c, delay_path_d
    # Select minimum cost path from u to v
    path_c = dijkstra(g_links, src, dst)
    # Check delay constraint
    cost_path_c = path_c['sum_cost']
    delay_path_c = path_c['sum_delay']
    # print("\tcost_path_c = %0.2f, delay_path_c = %0.2f") % (cost_path_c, delay_path_c)
    #print("\t--> Found a minimum cost path of (%s, %s)" % (src, dst))
    print("\t"),path_c
    if delay_path_c <= delay_bound:
        return path_c
    else:
        print("\tFinding another feasible path...")
        path_d = dijkstra(g_links, src, dst, -1)
        cost_path_d = path_d['sum_cost']
        delay_path_d = path_d['sum_delay']
        print("\tConsider: "), path_d
        # print("\tdelay_path_d = %0.2f, cost_path_d = %0.2f")%(delay_path_d, cost_path_d)
        if delay_path_d > delay_bound:
            print("\t--> Not satisfy delay-constrained")
            return None
        else:
            i = 0
            while True:
                i+=1
                lamda = round((cost_path_c - cost_path_d)/(delay_path_d - delay_path_c),2)
                print("\t\tlamda="), lamda
                path_lamda = dijkstra(g_links, src, dst, lamda)
                print("\t\t--> Found a minimum lamda cost path of (%s, %s)") % (sw1, sw2)
                print("\t\t"),path_lamda
                if round(path_lamda['sum_cost'],2) == round((cost_path_c + lamda * delay_path_c),2):
                    print("\t\tAccept:"),path_d
                    return path_d
                elif path_lamda['sum_delay'] <= delay_bound:
                    path_d = path_lamda
                    cost_path_d = round(path_lamda['sum_cost'],2)
                    delay_path_d = round(path_lamda['sum_delay'],2)
                    print("\t\tupdating cost_path_d = %0.2f, delay_path_d = %0.2f") % (cost_path_d, delay_path_d)
                else:
                    path_c = path_lamda
                    cost_path_c = round(path_lamda['sum_cost'],2)
                    delay_path_c = round(path_lamda['sum_delay'],2)
                    print("\t\tupdating cost_path_c = %0.2f, delay_path_c = %0.2f") % (cost_path_c, delay_path_c)

lst_all_devices = []
lst_all_devices_id = []
lst_all_links = {}


def get_resources():

    print ("Collecting resources...")
    beta = 0.5
    # Get all links
    query = "select id, sw1, sw2, delay_ms, loss_rate from links"
    cur.execute(query)
    for link in cur.fetchall():
        # Collect info of src
        query = "select delay_ms, population from devices where id='%s'" % (link[1])
        cur.execute(query)
        sw1_info = cur.fetchone()
        # Collect info of dest
        query = "select delay_ms, population from devices where id='%s'" % (link[2])
        cur.execute(query)
        sw2_info = cur.fetchone()
        # For larac_algorithm: cost = population * [(1-beta)*(dev_delay + link_delay) + beta*loss_rate]
        population = sw1_info[1]
        cost12 = round(population * ((1-beta)*(sw1_info[0] + link[3]) + beta*link[4]),2)
        cost21 = round(population * ((1-beta)*(sw2_info[0] + link[3]) + beta*link[4]),2)
        lst_all_links[link[0]] = [link[1], link[2], cost12, cost21, link[3], link[4]]

        # For developing myself
        # lst_all_links[link[0]] = [link[1], link[2], link[3], sw1_info[0], sw2_info[0], sw2_info[1]]


def remove_duplicates(values):
    output = []
    seen = set()
    for value in values:
        # If value has not been encountered yet,
        # ... add it to both list and set.
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output

def get_link_idx(lst_links, u, v):
    for idx in range(len(lst_links)):
        if lst_links[idx][1] == u and lst_links[idx][2] == v:
            return idx

def print_path(list_path):
    str_path = ""
    for item in list_path:
        str_path += item + '->'
    str_path = str_path.rstrip('->')
    print(str_path)

jsonStringGlobal = ""
def process_request(interval):
    # while True:
        get_resources()
        
        # Load all links to a list
        g_links = defaultdict(list)
        for v1, v2, cost12, cost21, delay, loss in lst_all_links.values():
            g_links[v1].append((cost12, delay, v2))
            g_links[v2].append((cost21, delay, v1))

        """ Generating random links for testing
        num_of_nodes = 125
        beta = 0.5
        result = genlink.gen_all_nodes_links(num_of_nodes, 0.0, 3.0, 2, 4)
        k = 1
        for i in range(1,num_of_nodes+1):
            for j in range(1,num_of_nodes+1):
                if i != j and result[i][j] != -1:
                    node = result[i][i]
                    link_delay = result[i][j]
                    link_cost = round(node[2] * ((1-beta)*(node[0] + link_delay) + beta*node[1]),2)
                    lst_all_links[k] = [i, j, link_cost, link_delay]
                    k+=1
        """
        lst_selected_devices = []
        lst_selected_regions = []
        # time.sleep(interval)
        # Get new request
        query = "select * from user_requests where status =  %d" % const.REQ_STATUS_NEW
        cur.execute(query)
        rows = cur.fetchall()
        if not rows:
            print('There is no request from user now')
            return
        # Handle each new request
        for row in rows:
            request = Request(row[0])
            print ('Processing request id: ' + str(request.id))
            # Get constraints
            delay_cons = row[3] # column delay in table user_request
            # Get list of covered device
            query = 'select a.id, a.device_id ' \
                    'from regions a join regions_of_request b ' \
                    'on a.id = b.region_id where b.usr_request_id = %s' % request.id
            cur.execute(query)
            for item in cur.fetchall():
                tmp_lst = set(lst_selected_regions)
                if item[0] not in tmp_lst:
                    lst_selected_regions.append(item[0])

                tmp_lst = set(lst_selected_devices)
                if item[1] not in tmp_lst:
                    lst_selected_devices.append(item[1])

                        # print "List of selected regions:"
            print(lst_selected_regions)
            print("List of selected devices:")
            print(lst_selected_devices)
            if len(lst_selected_devices) <= 0:
                print("The request is out of coverage")
                return
            request.update_db({'id': request.id, 'status': const.REQ_STATUS_NEW})
            lst_paths = []
            num_of_selected_device = len(lst_selected_devices)
            # Calculating minimum cost paths
            # switch_path = numpy.zeros(shape=(num_of_selected_device, num_of_selected_device))
            jsonString = "{"
            jsonStringUV = "\"resultuv\": ["
            jsonStringVU = "\"resultvu\": ["
            for i in range(0, num_of_selected_device - 1):
                for j in range(i + 1, num_of_selected_device):
                    u = lst_selected_devices[i]
                    v = lst_selected_devices[j]
                    lst_paths.extend(larac_alg(g_links, u, v, delay_cons)['path'])
                    print(("%s,%s,%s")%(u, v,lst_paths))
                    jsonStringUV = jsonStringUV + "{\"source\": \"" + u + "\", \"destination\": \"" + v + "\", \"nextHop\": " + str(lst_paths).replace("\'","\"") + "}, "
                    # resultReturn = "Finding path {%s} <--> {%s}...with result {%s}"%(lst_selected_switches[i], lst_selected_switches[j],lst_paths)
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):
                        print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z]))
                        # jsonStringUV = jsonStringUV + "{\"source\": \"" + lst_paths[0] + "\", " + "\"destination\": \"" + lst_paths[-1] + "\", " + "\"nextHop\": \"" + lst_paths[z] + "\"}, "
                    print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1]))
                    # return resultReturn   
                    lst_paths = []
                    # jsonString = jsonString[:-2]
                    # jsonString = jsonString + "], "
                    # jsonString = jsonString + "\"resultvu\": ["
                    
                    lst_paths.extend(larac_alg(g_links,v, u, delay_cons)['path'])
                    print(("%s,%s,%s")%(v, u, lst_paths))
                    jsonStringVU = jsonStringVU + "{\"source\": \"" + v + "\", \"destination\": \"" + u + "\", \"nextHop\": " + str(lst_paths).replace("\'","\"") + "}, "
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):
                        print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z]))
                        # jsonStringVU = jsonStringVU + "{\"source\": \"" + lst_paths[0] + "\", " + "\"destination\": \"" + lst_paths[-1] + "\", " + "\"nextHop\": \"" + lst_paths[z] + "\"}, "
                    print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1]))  
                    lst_paths = []
            jsonStringUV = jsonStringUV[:-2]
            jsonStringVU = jsonStringVU[:-2]
            jsonStringUV = jsonStringUV + "], "
            jsonStringVU = jsonStringVU + "]"
            # jsonString = jsonString[:-2]
            jsonString = jsonString + jsonStringUV + jsonStringVU + "}"
            # print("jsonString = ",jsonString)
            jsonLoad = json.loads(jsonString)
            # print("jsonLoad = ",jsonLoad)
            # print("resultuv from json = ", jsonLoad['resultuv'])
            jsonResult = jsonLoad['resultuv']
            i = 0
            for data in jsonResult:
                jsonDataLoad = json.loads(str(data).replace("\'","\""))
                print("resultuv from json with index %s = %s "%(i, jsonDataLoad))
                print("source = ", jsonDataLoad['source'])
                print("destination = ", jsonDataLoad['destination'])
                print("nextHop = ", jsonDataLoad['nextHop'])
                print("nextHop index 0 = ", jsonDataLoad['nextHop'][0])
                i = i + 1
            
            build_ovs_flow(jsonString)
                
def build_ovs_flow(jsonString):
    jsonLoad = json.loads(jsonString)
    jsonResult = jsonLoad['resultuv']
    arrayCheckSw = []
    
    i = 0
    for data in jsonResult:
        str_cmd = ""
        jsonDataLoad = json.loads(str(data).replace("\'","\""))
        jsonNextHop = jsonDataLoad['nextHop']
        x = 0
        for nextHop in jsonNextHop:
            swNH = jsonNextHop[x]
            checkSw = swNH in arrayCheckSw
            print(swNH + " in arrayCheckSw ===> " + str(checkSw))
            print("arrayCheckSw = " + str(arrayCheckSw))
            if checkSw == False:
                arrayCheckSw.append(swNH)
                str_cmd = "sudo ovs-ofctl  -O OpenFlow13 add-flow " + swNH 
                str_cmd = str_cmd + " \"priority=1,ip,nw_dst=10.0.0." + swNH[1:] + ",in_port=\"" + swNH + "-eth1\",actions=1\""
                print(str_cmd)
                os.system(str_cmd)
                x = x + 1
        i = i + 1
    #str_cmd = 'sudo ovs-ofctl add-flow -o OpenFlow13 %s "priority=2,ip,nw_dst=10.0.0.%d,in_port=2,actions=1"\n'
        # str_cmd_arp = 'sudo ovs-ofctl add-flow %s "priority=2,arp,in_port=%d,actions=%d"\n'
        # str_cmd = 'sudo ovs-ofctl add-flow %s ' \
        #     '"priority=2,arp,dl_dst=0:0:0:0:0:%d,in_port=%d,actions=%d"\n'
    

    

if __name__ == '__main__':
    print ("Start Main Process")
    #get_resources()
    process_request(5)
    topo = mininet_utils.MainTopo(lst_all_links)
    print('Generating topology ...')
    mininet_utils.generate(topo)


#    print ("Start Main Process")
#    get_resources()
#    print ("List of all links")
#    print (lst_all_links)
#    try:
#        threading._start_new_thread(process_request, (5,))
#    except:
#       print("Error: Unable to start thread")
#    while True:
#        pass
#    topo = mininet_utils.MainTopo(lst_all_links)
#    print('Generating topology...')
#    mininet_utils.generate(topo)
#    print ("End Main Process")
"""
#handle the request
def process_request(delay):
    global j
    while True:

        lst_selected_switches = []
        lst_selected_regions = []
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
            request.update_db({'id': request.id, 'status': 3})
            lst_paths = []
            num_of_selected_switches = len(lst_selected_switches)
            #switch_path = numpy.zeros(shape=(num_of_selected_switches, num_of_selected_switches))
            for i in range(0, num_of_selected_switches - 1):
                for j in range(i + 1, num_of_selected_switches):
                    u = lst_selected_switches[i]
                    v = lst_selected_switches[j]
                    lst_paths.extend(dijkstra(lst_all_links, u, v)['path'])
                    print(("%s,%s,%s")%(u, v,lst_paths))
                    # resultReturn = "Finding path {%s} <--> {%s}...with result {%s}"%(lst_selected_switches[i], lst_selected_switches[j],lst_paths)
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):

                        print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z]))
                    print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1]))
                    # return resultReturn   
                    lst_paths = []

                    lst_paths.extend(dijkstra(lst_all_links,v, u)['path'])
                    print(("%s,%s,%s")%(v, u, lst_paths))
                    count_lst_paths = len(lst_paths) - 1
                    for z in range(1, count_lst_paths):
                        print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[z]))
                    print(("[(source/forwarding) , (destination) , (next hop/sw)] == [%s,%s,%s]")%(lst_paths[0], lst_paths[-1], lst_paths[-1]))  
                    lst_paths = []
"""
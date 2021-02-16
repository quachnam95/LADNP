import requests
from requests.auth import HTTPBasicAuth
import urllib3
import config
import xml.etree.ElementTree as ET
from copy import deepcopy

# url = "http://192.168.0.7.101:8181/restconf/operational/opendaylight-inventory:nodes/node/openflow:1/table/0"
# http://192.168.0.7:8181/restconf/config/opendaylight-inventory:nodes/node/openflow:1/table/0/flow/L2switch-3
namespace = "urn:opendaylight:flow:inventory"
basic_auth = HTTPBasicAuth('admin', 'admin')
headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml'
            # 'Accept': 'application/yang.data+json',
            # 'Content-Type': 'application/yang.data+json'
        }
# rq = requests.get(url, auth=acc)
# print(type(rq))
# print(rq.status_code)
# print(rq.headers)
# print(rq.headers['content-type'])
# print(rq.text)

template = 'flow_template.xml'
parser = ET.XMLParser(encoding="utf-8")

def retrieve_flow_ids(node_id, table_id):
    lst_flow_ids = []
    url = "http://"+config.SDN_CONTROLLER+":8181/restconf/operational/opendaylight-inventory:nodes/node/openflow:%d/table/%d"\
                 % (node_id, table_id)
    rq = requests.get(url=url, auth=basic_auth)
    data = rq.text
    if rq.status_code == 200 and data:
        tree = ET.fromstring(data)
        for flow in tree.findall('{'+namespace+'}flow'):
            flow_id = flow.find('{'+namespace+'}id').text
            lst_flow_ids.append(flow_id)
    else:
        print("Error while retrieving data")
    return lst_flow_ids

def build_flow_data(flow_id, in_port, output, table_id=0):
    ET.register_namespace("", namespace)
    templ = ET.parse(template)
    tree = deepcopy(templ)
    root = tree.getroot()
    # children = root.getchildren()
    # sh = tree.find(<name_node>)
    # sh_value = sh.text
    # sh.get(<attribute>)
    # sh.set(<attribute>, <value>)
    nodes = root.iter()
    for node in nodes:
        if node.tag == ("{%s}priority" % namespace):
            node.text = '5'
        if node.tag == ("{%s}flow-name" % namespace):
            node.text = 'MyFlow-%s' % flow_id
        if node.tag == ("{%s}id" % namespace):
            node.text = str(flow_id)
        if node.tag == ("{%s}table_id" % namespace):
            node.text = str(table_id)
        if node.tag == ("{%s}in-port" % namespace):
            node.text = str(in_port)
        if node.tag == ("{%s}output-node-connector" % namespace):
            node.text = str(output)
    tree.write("test.xml", encoding="UTF-8", xml_declaration=True)
    data = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    data += ET.tostring(root)
    return data

def push_flows(path, sw_port_matrix):
    common_url = "http://"+ config.SDN_CONTROLLER+":8181/restconf/config/opendaylight-inventory:nodes/node/openflow:%d/table/%d/flow/%s"
    for si in range(0, len(path)):
        num_of_flows = [1 for x in range(len(sw_port_matrix[0])+1)]
        sw = path[si]
        sw_idx = int(sw[1:])
        table_id = 0
        if si < 1:
            inport = sw_port_matrix[int(path[si][1:])][int(path[si][1:])]
            output = sw_port_matrix[int(path[si][1:])][int(path[si + 1][1:])]
        elif si < len(path) - 1:
            inport = sw_port_matrix[int(path[si][1:])][int(path[si - 1][1:])]
            output = sw_port_matrix[int(path[si][1:])][int(path[si + 1][1:])]
        else:
            inport = sw_port_matrix[int(path[si][1:])][int(path[si - 1][1:])]
            output = sw_port_matrix[int(path[si][1:])][int(path[si][1:])]
        lst_existed_flows = retrieve_flow_ids(sw_idx, table_id)
        for fl_id in lst_existed_flows:
            print("Delete flow %s" % fl_id)
            url = common_url % (sw_idx, table_id, fl_id)
            response = requests.delete(url, headers=headers, auth=basic_auth)
            if not response.status_code in range(200, 300):
                print("Delete flow %s error" % fl_id)
        print("Pushing flow to %s" % sw)
        # flow from sw toward to next-hop
        flow_id = 'F-' + str(num_of_flows[sw_idx])
        url = common_url % (sw_idx, table_id, flow_id)
        data = build_flow_data(flow_id, inport, output, table_id)
        response = requests.put(url, data=data, headers=headers, auth=basic_auth)
        if response.status_code in range(200, 300):
            num_of_flows[sw_idx] += 1
        else:
            print("ERROR1")
        # flow from next-hop back to sw
        flow_id = 'F-' + str(num_of_flows[sw_idx])
        url = common_url % (sw_idx, table_id, flow_id)
        data = build_flow_data(flow_id, output, inport, table_id)
        response = requests.put(url, data=data, headers=headers, auth=basic_auth)
        if response.status_code in range(200, 300):
            num_of_flows[sw_idx] += 1
        else:
            print("ERROR2")

retrieve_flow_ids(1, 0)
#!/usr/bin/python
import os
import config
# mininet libraries
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI

class SingleTopo(Topo):
    "N hosts connected to single switch"
    def __init__(self, device, lstHosts, **opts):
        # Initialize topo and default option
        Topo.__init__(self, **opts)
        hosts = []

        switch = self.addSwitch(device, protocols='OpenFlow13')
        # Create devices
        for host in lstHosts:
            self.addLink(self.addHost(host), switch)

class MeshTopo(Topo):
    "N switches connected to each other (mapping switch:host is 1:1)"
    def __init__(self, lst_all_device, lst_selected_devices, **opts):
        # Initialize topo and default option
        Topo.__init__(self, **opts)

        switches = []
        # print lstAllDevices
        # print lstSelectedDevices
        for dev in lst_all_device:
            switch = self.addSwitch(dev.id, protocols='OpenFlow13')
            # host = self.addHost('h%s' % dev.id)
            # self.addLink(host, switch)
            if dev.id in lst_selected_devices:
                switches.append(switch)
                host = self.addHost('h%s' % dev.id)
                self.addLink(host, switch)
        
        numOfSwiches = len(switches)
        if numOfSwiches > 0:
            i = 0
            while i < numOfSwiches-1:
                for j in range(i+1, numOfSwiches):
                    self.addLink(switches[i], switches[j])
                i += 1
        else:
            print("There is no switch covered selected regions")

class MainTopo(Topo):
    def __init__(self, lst_links, **opts):
        Topo.__init__(self, **opts)
        hosts_switches = {}
        # print lst_links
        # Create switches and links among them
        for link in lst_links.values():
            sw1 = self.addSwitch(link[0], protocols='OpenFlow13')
            hosts_switches[sw1] = ('h%s'%sw1[1:], "10.0.0.%s"%sw1[1:])

            sw2 = self.addSwitch(link[1], protocols='OpenFlow13')
            hosts_switches[sw2] = ('h%s'%sw2[1:], "10.0.0.%s"%sw2[1:])

            self.addLink(sw1, sw2, bw=10, delay=str(link[4])+'ms', loss=link[5])
        # Create a host attaching to each switch
        for key, value in hosts_switches.items():
            switch = key
            host = self.addHost(value[0], ip=value[1])
            self.addLink(switch, host)

def generate(Topo):
    setLogLevel('info')
    print('Cleaning up ...')
    os.system('sudo mn -c')
    net = Mininet(topo=Topo, controller=None, link=TCLink)
    net.addController('c0', controller=RemoteController, ip=config.SDN_CONTROLLER, port=config.SDN_PORT)
    net.start()
    print("Dumping host connections")
    dumpNodeConnections(net.hosts)
    print("Dumping switch connections")
    dumpNodeConnections(net.switches)
    # print("Testing network connectivity")
    # net.pingAll()
    #CLI(net)
    # net.stop()


# def createFlowTable(paths):
#     src = paths[0]
#     dst = paths[-1]
#     for i in range (0, len(paths)-1):
#         for j in range (i+1, len(paths)):


#!/usr/bin/env python
#
# Copyright 2010,2011 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

from gnuradio import gr, gru, uhd
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio.gr import firdes
import gnuradio.extras as gr_extras
import precog

# From gr-digital
from gnuradio import digital

import struct
import sys
import threading
import time
from ctypes import *

# socket 
import socket

#import os
#print os.getpid()
#raw_input('Attach and press enter: ')

DEBUG = 0

ds = 32

NETWORK_SIZE = 4  # the number of all the USRPs

MTU = 4096

BURST_LEN = 0.008  #burst duration = 8ms
NODES_PC  = 2

CLUSTER_HEAD    = 'head'   # cluster head
CLUSTER_NODE    = 'node'   # cluster node

HEAD_PORT = 23000   # port where cluster head capturing the socket message
NODE_PORT = 23001   # port where cluster node capturing the socket message

# thread for getting transmitted data from file or orther source
class tx_data_src(threading.Thread):
    def __init__(self, tx_path):
        threading.Thread.__init__(self)
        self._txpath = tx_path
        
    def run(self):
        #generate and send packets
        n = 0
        pktno = 0
        #pkt_size = int(options.size)
        print "tx_data_src -%s start tx" %(self.getName())
        while 1:
            data = (50 - 2) * chr(pktno & 0xff)
            payload = struct.pack('!H', pktno & 0xffff) + data
            self._txpath.send_pkt(payload, False)
            n += len(payload)
            #sys.stderr.write('.')
            pktno += 1

# Socket Control Channel 
class socket_server(threading.Thread):
    def __init__(self, port, parent):
        threading.Thread.__init__(self)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('', port))
        self._parent = parent
          
    def run(self):
        while 1:
            msg, (addr, port) = self._socket.recvfrom(MTU)
            
            current_time = self._parent._owner.rcvs[0].get_time_now().get_real_secs()
            print "msg received at time of %.7f" %current_time
            print msg
            
            payload = msg
            cmds = []
            l = len(payload)
            pos2 = 0
            pos1 = payload.find(':', 0, len(payload))
	    
            while(pos1 != -1):
                cmds.append(payload[pos2:pos1])
                pos2 = pos1 + 1
                pos1 = payload.find(':', pos2, len(payload))

                if(pos1 == -1):
                    cmds.append(payload[pos2:len(payload)])	    
	    
            if(len(cmds) == 0):
                continue
	       
            if(cmds[0] == 'cmd'):    
                if(cmds[1] == 'start' and len(cmds) == 5):
                        (start_time, ) = struct.unpack('!d', cmds[2])
                        (burst_duration, ) = struct.unpack('!d', cmds[3])
                        (idle_duration, ) = struct.unpack('!d', cmds[4])
			# handle the start command
                        self._parent._owner.start_tdma_net(start_time, burst_duration, idle_duration)
	        else:
	            print 'protocol error'
			
class socket_client(object):
    def __init__(self, dest_addr, dest_port, parent):
	    self._parent = parent
	    self._dest_addr = dest_addr
	    self._dest_port = dest_port
	    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		
    def set_dest(self, dest_addr, dest_port):
	    self._dest_addr = dest_addr
	    self._dest_port = dest_port

class socket_ctrl_channel(object):
	def __init__(self, head_or_node, owner):
	    self._owner = owner #
	    if (head_or_node == CLUSTER_HEAD): # head
	       self._sock_server = socket_server(HEAD_PORT, self)
	       self._sock_client = socket_client('', NODE_PORT, self)
	    else:  # node
	       self._sock_server = socket_server(NODE_PORT, self)
	       self._sock_client = socket_client('', HEAD_PORT, self)
		   
class my_top_block(gr.top_block):        
    def start_streaming(self):
        if self._node_type == CLUSTER_HEAD:
            #self._socket_ctrl_chan._sock_client._socket.sendto("message from cluster head\n", ('<broadcast>', NODE_PORT))
            hostname = socket.gethostname()
            current_time = self.rcvs[0].get_time_now().get_real_secs()
            start_time_v = current_time + 10
            print "cluster head current time %.7f" %current_time
            start_time = struct.pack('!d', current_time + 10)        
            burst_duration = struct.pack('!d', BURST_LEN)
            t_slot = 0.010  # tdma slot length
            idle_duration = struct.pack('!d', t_slot*(NETWORK_SIZE - 1) + t_slot - BURST_LEN)
            payload = 'cmd' + ':' + 'start' + ':' + start_time + ':' + burst_duration + ':' + idle_duration 
            #print hostname
            #self._socket_ctrl_chan._sock_client._socket.sendto(hostname, ('<broadcast>', NODE_PORT))
            self._socket_ctrl_chan._sock_client._socket.sendto(payload, ('<broadcast>', NODE_PORT))

            #self.rcvs[0].set_start_time(uhd.time_spec_t(start_time_v))
            self.rcvs[0].start()
        else:  # CLUSTER_NODE will be responsible for tdma transmitting and receiving
            if DEBUG == 1:
                stime = self.rcvs[0].get_time_now().get_real_secs()
                #for i in range(NODES_PC):                      
                self.rcvs[0].set_start_time(uhd.time_spec_t(stime + 2))
                self.start()
                time.sleep(5)
                self.rcvs[0].start()
        
    def __init__(self, node_type, node_index, demodulator, modulator, rx_callback, options):
        gr.top_block.__init__(self)
		
        # is this node the sub node or head?
        self._node_type = node_type
        self._node_id   = node_index	

        # install the socket control channel
        self._socket_ctrl_chan = socket_ctrl_channel(self._node_type, self)
        # start the socket server to capture the control messages
        self._socket_ctrl_chan._sock_server.start()
        
        self.link_rate = options.link_rate
        self.sample_rate = options.samp_rate
        self.center_freq = options.center_freq
        self.rx_gain = options.rx_gain
        self.tx_gain = options.tx_gain 

        #setup the flowgraphs
        self.find_all_devices()
        self.setup_usrp_sources()
        
        if(self._node_type == CLUSTER_NODE):
            self.setup_tdma_engines()
            self.setup_packet_framers()
            self.setup_bpsk_mods()
            self.setup_multiply_consts()
            self.setup_burst_gates()
            self.setup_usrp_sinks()
            self.setup_bpsk_demods()
            self.setup_packet_deframers()
            self.make_all_connections()
        elif(self._node_type == CLUSTER_HEAD):
            self.filesink = gr.file_sink(gr.sizeof_gr_complex, "file.dat")
            self.connect((self.rcvs[0], 0), self.filesink)

        self.timer =  threading.Timer(1, self.start_streaming)
    
    def find_all_devices(self):
        # configuration the usrp sensors and transmitters
        # Automatically USRP devices discovery
        self.devices = uhd.find_devices_raw()
        self.n_devices = len(self.devices)
        self.addrs = []
        
        if (self.n_devices == 0):
            sys.exit("no connected devices")
        elif (self.n_devices >= 1):
            for i in range(self.n_devices):
                addr_t = self.devices[i].to_string()  #ex. 'type=usrp2,addr=192.168.10.109,name=,serial=E6R14U3UP'
                self.addrs.append(addr_t[11:30]) # suppose the addr is 192.168.10.xxx
                self.addrs[i]
                
        #if (self.n_devices == 1 and self._node_type == CLUSTER_NODE):
            #sys.exit("only one devices for the node, we need both communicator and sensor for cluster node")
        if (self.n_devices > 1 and self._node_type == CLUSTER_HEAD):
            sys.exit("only one devices is need for cluster head")
   
    
    def setup_usrp_sources(self):
        print 'setup_usrp_sources'
        self.rcvs = []
        for i in range(self.n_devices):
            self.rcvs.append(uhd.usrp_source(self.addrs[i],
                                             stream_args=uhd.stream_args(
				                         cpu_format="fc32",
				                         channels=range(1),
			                                 ),
			                    )
			    )
            if(self._node_type == CLUSTER_NODE):			    
                self.rcvs[i].set_start_on_demand()  # the sensor will start sensing onmand												
            if self.rcvs[i].get_time_source(0) == "none":
                self.rcvs[i].set_time_source("mimo", 0)  # Set the time source without GPS to MIMO cable
                self.rcvs[i].set_clock_source("mimo",0)
            self.rcvs[i].set_samp_rate(self.sample_rate)
	    self.rcvs[i].set_center_freq(self.center_freq, 0)
	    self.rcvs[i].set_gain(self.rx_gain, 0)
	    self.rcvs[i].set_antenna("TX/RX", 0)        
    
    def setup_bpsk_mods(self):
        print 'setup_bpsk_mods'
        self.bpskmods = []
        for i in range(self.n_devices):
            self.bpskmods.append(digital.bpsk.bpsk_mod(samples_per_symbol=2,
                                                       log=True))
    
    def setup_packet_deframers(self):
        print 'setup_packet_deframers'
        self.pktdfrms = []
        for i in range(self.n_devices):
            self.pktdfrms.append(precog.packet_deframer(access_code=None,
                                                          threshold=-1,))
    
    def setup_tdma_engines(self):
        print ' setup_tdma_engines'
        self.tdmaegns = []
        for i in range(self.n_devices):
            initial_slot = NODES_PC*self._node_id + i
            number_of_slots = NETWORK_SIZE
            self.tdmaegns.append(precog.tdma_engine(initial_slot,
                                                    0.050,#options.slot_interval,
                                                    0.010,#options.guard_interval,
                                                    number_of_slots,#options.number_of_slots,
                                                    0.005,#options.lead_limit,
                                                    self.link_rate))
    
    def setup_packet_framers(self):
        print ' setup_packet_framers'
        self.pktfrms = []
        for i in range(self.n_devices):
            self.pktfrms.append(precog.packet_framer(samples_per_symbol=2,
		                                        bits_per_symbol=1,
		                                        access_code=None,
		                                       ))
    
    def setup_bpsk_demods(self):
        print 'setup_bpsk_demods'
        self.bpskdemods = []
        for i in range(self.n_devices):
            self.bpskdemods.append(digital.bpsk.bpsk_demod(samples_per_symbol=2,
                                                           log=True))
    
    def setup_multiply_consts(self):
        print 'setup_multiply_consts'
        self.mlts = []
        for i in range(self.n_devices):
            self.mlts.append(gr.multiply_const_vcc((0.7, )))
    
    def setup_burst_gates(self):
        print 'setup_burst_gates'
        self.bstgts = []
        for i in range(self.n_devices):
            self.bstgts.append(precog.burst_gate())
    
    def setup_usrp_sinks(self):
        print 'setup_usrp_sinks'
        self.sinks = []
        for i in range(self.n_devices):
            self.sinks.append(uhd.usrp_sink(self.addrs[i],
			                    stream_args=uhd.stream_args(cpu_format="fc32",
                                                                        channels=range(1),
                                                                       ),
                                           )
                             )
            self.sinks[i].set_samp_rate(self.sample_rate)
	    self.sinks[i].set_center_freq(self.center_freq, 0)
            if(self.tx_gain):
	        self.sinks[i].set_gain(self.tx_gain, 0)
	    self.sinks[i].set_antenna("TX/RX", 0)
    
    def make_all_connections(self):
        print 'make all connections'
        for i in range(self.n_devices):
            # Trasnmitting Path
            self.connect((self.rcvs[i], 0), (self.tdmaegns[i], 0))
            self.connect((self.tdmaegns[i], 0), (self.pktfrms[i], 0))
            self.connect((self.pktfrms[i], 0), (self.bpskmods[i], 0))
            self.connect((self.bpskmods[i], 0), (self.mlts[i], 0))
            self.connect((self.mlts[i], 0), (self.bstgts[i], 0))
            self.connect((self.bstgts[i], 0), (self.sinks[i], 0))
            # Receiving Path
            self.connect((self.rcvs[i], 0), (self.bpskdemods[i], 0))
            self.connect((self.bpskdemods[i], 0), (self.pktdfrms[i], 0))
            self.connect((self.pktdfrms[i], 0), (self.tdmaegns[i], 2))
            
	
    def start_tdma_net(self, start_time, burst_duration, idle_duration):
        # specify the tdma pulse parameters and connect the 
        # pulse source to usrp sinker also specify the usrp source
        # with the specified start time
        if (self.n_devices > 0):
            time_slot = (burst_duration + idle_duration)/NETWORK_SIZE
            #print 'base_s_time = %.7f' %start_time
            for i in range(self.n_devices):
                s_time = uhd.time_spec_t(start_time + time_slot*(NODES_PC*self._node_id + i))
                #print 'specified_time = %.7f' %s_time.get_real_secs()
                local_time = self.rcvs[i].get_time_now().get_real_secs()
                print 'current time 1 = %.7f' %local_time
		# Set the start time for sensors                
		self.rcvs[i].set_start_time(uhd.time_spec_t(start_time))
        else:
            exit("no devices on this node!")
			
        # start the flow graph and all the sensors
        self.start()
        time.sleep(5)
        for i in range(self.n_devices):
            current_time = self.rcvs[i].get_time_now().get_real_secs()
            print "current time 2 = %.7f" %current_time
            #print "base_s_time = %.7f" %start_time
            self.rcvs[i].start()
            #start the transmitting of data packets
            self.sinks[i].start()

# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

global n_rcvd, n_right

def main():
    global n_rcvd, n_right
    
    n_rcvd = 0
    n_right = 0

    node_types = {}
    node_types["head"] = "head"
    node_types["node"] = "node"	
 
    def rx_callback(ok, payload):
        global n_rcvd, n_right
        (pktno,) = struct.unpack('!H', payload[0:2])
        n_rcvd += 1
        if ok:
            n_right += 1

        print "ok = %5s  pktno = %4d  n_rcvd = %4d  n_right = %4d" % (
            ok, pktno, n_rcvd, n_right)
            
    demods = digital.modulation_utils.type_1_demods()
    mods   = digital.modulation_utils.type_1_mods()

    # Create Options Parser:
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-m", "--modulation", type="choice", choices=demods.keys(), 
                      default='psk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(demods.keys()),))
    parser.add_option("-s", "--size", type="eng_float", default=100,
                      help="set packet size [default=%default]")
    parser.add_option("","--from-file", default=None,
                      help="input file of samples to demod")

    parser.add_option("", "--node-type", type="choice", choices=node_types.keys(),
                          default="node",
                          help="Select node type from: %s [default=%%default]"
                                % (', '.join(node_types.keys()),))
    parser.add_option("-i", "--node-index", type="intx", default=0, 
                          help="Specify the node index in the cluster [default=%default]")
                          
    ###############################
    # Options for radio parameters
    ###############################
    parser.add_option("-l", "--link-rate", type="eng_float", default=None,
                      help="specify the link data rate")
    parser.add_option("", "--samp-rate", type="eng_float", default=None,
                      help="specify the sample rate for the USRP")
    parser.add_option("-f", "--center-freq", type="eng_float", default=None,
                      help="specify the cetner frequency for the USRP")
    parser.add_option("", "--tx-gain", type="eng_float", default=None,
                      help="specify the tx gain for the USRP")                  					  
    parser.add_option("", "--rx-gain", type="eng_float", default=None,
                      help="specify the rx gain for the USRP")    
					  
    for mod in demods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()

    if len(args) != 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # build the graph
    tb = my_top_block(node_types[options.node_type],
                    options.node_index,
                    demods[options.modulation],
                    mods[options.modulation], 
		    rx_callback, options)

    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: Failed to enable realtime scheduling."
    
    #tb.start()        # start flow graph
    #self.source.u.stop()
    #time.sleep(10)
    tb.timer.start()
    #tb.source.u.start()
    
    #tb.wait()         # wait for it to finish

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

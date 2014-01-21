#
# Copyright 1980-2012 Free Software Foundation, Inc.
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

import numpy
from math import pi
from gnuradio import gr
from gruel import pmt
from gnuradio.digital import packet_utils
import gnuradio.digital as gr_digital
import gnuradio.extras #brings in gr.block
from gnuradio.extras import extras_swig
import Queue
import time
import math
import struct

BROADCAST_ADDR = 255

#block port definitions - inputs
OUTGOING_PKT_PORT = 0
INCOMING_PKT_PORT = 1
CTRL_PORT = 2

#block port definitions - outputs
TO_FRAMER_PORT = 0
CTRL_PORT = 1

#Time state machine
LOOKING_FOR_TIME = 0 
HAVE_TIME = 0

pn511_0 = '\x82\x5B\x8E\x63\xE0\xAA\xCA\xE8\xD5\x1D\x26\x8A\xD4\xFC\x6D\x0B\xBD\x40\xCC\x8C\xB0\x99\xE9\xC4\xF3\x67\x57\xB6\x0D\x29\x80\x88\xF7\x20\xEE\xB1\x78\xA2\x45\x9A\xDB\xF6\x31\x00\xF0\xA5\xC0\xB4\xDE\x50\xC3\x86\xEC\x92\xA4\x21\xFF\x5F\x39\x7F\x27\x6B\x9F\x7C'

pn511_1 = '\x82\x04\xC4\xF7\xA8\x39\xE3\x87\x97\xB1\x96\x2B\x6A\xA5\xB9\x85\x38\xB4\x05\x5E\x0B\x26\xEA\xC3\x06\xA6\x8C\x7C\x25\x12\x44\x5C\x69\x5D\x3E\xDF\xF7\x65\x47\xA4\xEE\x07\xF1\x0E\xB5\x9F\xA2\x85\xF5\xCA\x42\x37\x9B\x66\x72\x5D\xF3\xA1\xB0\x0C\xD7\xE4\x76\x98'

pn511s = [pn511_0, pn511_0]


# /////////////////////////////////////////////////////////////////////////////
#                   TDMA MAC
# /////////////////////////////////////////////////////////////////////////////

class tdma_engine(gr.block):
    """
    TDMA implementation.  See wiki for more details
    """
    def __init__(
        self,initial_slot,slot_interval,guard_interval,num_slots,lead_limit,link_bps,tx_addr,from_file, mimo
    ):
        """
        Inputs: complex stream from USRP, pkt in, ctrl in
        Outputs: pkt out, ctrl out
        """

        gr.block.__init__(
            self,
            name = "tdma_engine",
            in_sig = [numpy.complex64],
            out_sig = None,
            num_msg_inputs = 3,
            num_msg_outputs = 2,
        )

        self.mgr = pmt.pmt_mgr()
        for i in range(64):
            self.mgr.set(pmt.pmt_make_blob(10000))
        
        self.initial_slot = initial_slot
        self.num_slots = num_slots
        self.prefix_loc = 0
        self.prefix_len = 1
        if mimo == True:
            self.prefix_loc = initial_slot
            print 'prefix_loc = %d' %(self.prefix_loc)
            self.prefix_len = 2 # number of PNs
            self.initial_slot = 1
        self.slot_interval = slot_interval
        self.guard_interval = guard_interval
        self.lead_limit = lead_limit
        self.link_bps = link_bps
	self.tx_addr = tx_addr
        self.from_file = from_file
        
        self.bytes_per_slot = int( ( self.slot_interval - self.guard_interval ) * self.link_bps / 8 )
        
        self.queue = Queue.Queue()                        #queue for msg destined for ARQ path
        self.tx_queue = Queue.Queue()
        
        self.last_rx_time = 0
        self.last_rx_rate = 0
        self.samples_since_last_rx_time = 0
        
        self.next_interval_start = 0
        self.next_transmit_start = 0

        self.know_time = False
        self.found_time = False
        self.found_rate = False
        self.set_tag_propagation_policy(extras_swig.TPP_DONT)

        self.has_old_msg = False
        self.overhead = 15
        #self.pad_data = numpy.fromstring('this idsaf;lkjkfdjsd;lfjs;lkajskljf;klajdsfk',dtype='uint8')
        self.pktno = 0

        if self.from_file:
            txfile_name = '/home/alexzh/' + self.tx_addr + '_randtx'
            self.sfile = open(txfile_name, 'r')
        
        self.tx_slots_passed = 0
    
    def tx_frames(self):
        #send_sob
        #self.post_msg(TO_FRAMER_PORT, pmt.pmt_string_to_symbol('tx_sob'), pmt.PMT_T, pmt.pmt_string_to_symbol('tx_sob'))

        #get all of the packets we want to send
        total_byte_count = 0
        frame_count = 0
        
        #put residue from previous execution
        if self.has_old_msg:
            length = len(pmt.pmt_blob_data(self.old_msg.value)) + self.overhead
            total_byte_count += length
            self.tx_queue.put(self.old_msg)
            frame_count += 1
            self.has_old_msg = False
            print 'old msg'

        #fill outgoing queue until empty or maximum bytes queued for slot
        while(not self.queue.empty()):
            msg = self.queue.get()
            length = len(pmt.pmt_blob_data(msg.value)) + self.overhead
            total_byte_count += length
            if total_byte_count >= self.bytes_per_slot:
                self.has_old_msg = True
                self.old_msg = msg
                print 'residue'
                continue
            else:
                self.has_old_msg = False
                self.tx_queue.put(msg)
                frame_count += 1
        
        time_object = int(math.floor(self.antenna_start)),(self.antenna_start % 1)
        
        #if no data, send a single pad frame
        #TODO: add useful pad data, i.e. current time of SDR
        if frame_count == 0:
            #pad_d = struct.pack('!H', self.pktno & 0xffff) + (self.bytes_per_slot - 100) * chr(self.pktno & 0xff)
            512zeros = 64*chr(0x00)
            prefix = ''
            for i in range(self.prefix_len):
                if i == self.prefix_loc:
                    seg = 512zeros + pn511s[i]  #put the PN code to the prefix
                else:
                    seg = 128*chr(0x00)
                # the prefix looks like  0000000...0000PPPPPP...PPPP0000000.....000000
                #                        |___512bit_||____512bit_||___M*1024bit_____|
                # M+N+1 := num_slots
                # N+1 := prefix_loc
                prefix = prefix + seg

            if self.from_file and self.sfile != 0:
                rdata = self.sfile.read(self.bytes_per_slot - 100)
                if len(rdata) > 0:
                    pad_d = rdata
            else:
                if self.initial_slot == 0:
                    pad_d = 16*pn511_0 #+ (self.bytes_per_slot - 64) * chr(self.pktno & 0xff)
                else:
                    pad_d = 16*pn511_1
            pad_d = prefix + '\x00\x00\x00\x00' + pad_d

            data  = numpy.fromstring(pad_d, dtype='uint8')
            #data = self.pad_data
            #data = pad_d
            more_frames = 0
            tx_object = time_object,data,more_frames

            print 'prefix_loc = %d' %(self.prefix_loc)
            print 'antenna_start = %7f' %(self.antenna_start)

            self.post_msg(TO_FRAMER_PORT,pmt.pmt_string_to_symbol('full'),pmt.from_python(tx_object),pmt.pmt_string_to_symbol('tdma'))
            self.pktno += 1
            #print 'tx_frames:post message from the pad data'
        else:
            #print frame_count,self.queue.qsize(), self.tx_queue.qsize()
            #send first frame w tuple for tx_time and number of frames to put in slot
            blob = self.mgr.acquire(True) #block
            more_frames = frame_count - 1
            msg = self.tx_queue.get()
            data = pmt.pmt_blob_data(msg.value)
            tx_object = time_object,data,more_frames
            self.post_msg(TO_FRAMER_PORT,pmt.pmt_string_to_symbol('full'),pmt.from_python(tx_object),pmt.pmt_string_to_symbol('tdma'))
            frame_count -= 1
            
            
            old_data = []
            #print 'frame count: ',frame_count
            #send remining frames, blob only
            while(frame_count > 0):
                msg = self.tx_queue.get()
                data = pmt.pmt_blob_data(msg.value)
                blob = self.mgr.acquire(True) #block
                pmt.pmt_blob_resize(blob, len(data))
                pmt.pmt_blob_rw_data(blob)[:] = data
                self.post_msg(TO_FRAMER_PORT,pmt.pmt_string_to_symbol('d_only'),blob,pmt.pmt_string_to_symbol('tdma'))
                frame_count -= 1
        
        #print total_byte_count
        
    def work(self, input_items, output_items):
        #check for msg inputs when work function is called
        if self.check_msg_queue():
            try: msg = self.pop_msg_queue()
            except: return -1

            if msg.offset == OUTGOING_PKT_PORT:
                self.queue.put(msg)                 #if outgoing, put in queue for processing
            elif msg.offset == INCOMING_PKT_PORT:
                a = 0                               #TODO:something intelligent for incoming time bcast pkts
            else:
                a = 0                               #CONTROL port
            
        #process streaming samples and tags here
        in0 = input_items[0]
        nread = self.nitems_read(0) #number of items read on port 0
        ninput_items = len(input_items[0])

        #read all tags associated with port 0 for items in this work function
        tags = self.get_tags_in_range(0, nread, nread+ninput_items)

        #lets find all of our tags, making the appropriate adjustments to our timing
        for tag in tags:
            key_string = pmt.pmt_symbol_to_string(tag.key)
            if key_string == "rx_time":
                self.samples_since_last_rx_time = 0
                self.current_integer,self.current_fractional = pmt.to_python(tag.value)
                self.time_update = self.current_integer + self.current_fractional
                self.found_time = True
            elif key_string == "rx_rate":
                self.rate = pmt.to_python(tag.value)
                self.sample_period = 1/self.rate
                self.found_rate = True
        
        #determine first transmit slot when we learn the time
        if not self.know_time:
            if self.found_time and self.found_rate:
                self.know_time = True
                self.frame_period = self.slot_interval * self.num_slots
                my_fraction_frame = ( self.initial_slot * 1.0 ) / ( self.num_slots)
                frame_count = math.floor(self.time_update / self.frame_period)
                current_slot_interval = ( self.time_update % self.frame_period ) / self.frame_period
                self.time_transmit_start = (frame_count + 2) * self.frame_period + ( my_fraction_frame * self.frame_period ) - self.lead_limit
        
        #get current time
        self.time_update += (self.sample_period * ninput_items)

        #determine if it's time for us to start tx'ing, start process self.lead_limit seconds
        #before our slot actually begins (i.e. deal with latency)
        if self.time_update > self.time_transmit_start:
            self.interval_start = self.time_transmit_start + self.lead_limit
            self.antenna_start = self.interval_start + self.guard_interval
            self.tx_frames()  #do more than this?
            self.time_transmit_start += self.frame_period
            #TODO: add intelligence to handle slot changes safely
            
        return ninput_items

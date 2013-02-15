#!/usr/bin/env python
##################################################
# Gnuradio Python Flow Graph
# Title: TDMA_HIER
# Author: John Malsbury
# Description: USRP TDMA Implementation
# Generated: Fri Feb 15 00:16:16 2013
##################################################

from gnuradio import digital
from gnuradio import gr
from gnuradio import uhd
from gnuradio.gr import firdes
import gnuradio.extras as gr_extras
import precog

class tdma_hier(gr.hier_block2):

	def __init__(self, rx_gain=15, rate=1e6, samp_per_sym=4, args="", freq=915e6, ampl=0.7, tx_gain=15, number_of_slots=10, lead_limit=0.025, initial_slot=15, link_speed=15, slot_interval=0.010, guard_interval=15):
		gr.hier_block2.__init__(
			self, "TDMA_HIER",
			gr.io_signaturev(2, 2, [gr.sizeof_char*1, gr.sizeof_char*1]),
			gr.io_signaturev(2, 2, [gr.sizeof_char*1, gr.sizeof_char*1]),
		)

		##################################################
		# Parameters
		##################################################
		self.rx_gain = rx_gain
		self.rate = rate
		self.samp_per_sym = samp_per_sym
		self.args = args
		self.freq = freq
		self.ampl = ampl
		self.tx_gain = tx_gain
		self.number_of_slots = number_of_slots
		self.lead_limit = lead_limit
		self.initial_slot = initial_slot
		self.link_speed = link_speed
		self.slot_interval = slot_interval
		self.guard_interval = guard_interval

		##################################################
		# Variables
		##################################################
		self.samp_rate = samp_rate = rate

		##################################################
		# Blocks
		##################################################
		self.usrp_source = uhd.usrp_source(
			device_addr=args,
			stream_args=uhd.stream_args(
				cpu_format="fc32",
				channels=range(1),
			),
		)
		self.usrp_source.set_time_source("external", 0)
		self.usrp_source.set_time_unknown_pps(uhd.time_spec())
		self.usrp_source.set_samp_rate(samp_rate)
		self.usrp_source.set_center_freq(freq, 0)
		self.usrp_source.set_gain(rx_gain, 0)
		self.usrp_source.set_antenna("TX/RX", 0)
		self.usrp_sink = uhd.usrp_sink(
			device_addr=args,
			stream_args=uhd.stream_args(
				cpu_format="fc32",
				channels=range(1),
			),
		)
		self.usrp_sink.set_time_source("external", 0)
		self.usrp_sink.set_time_unknown_pps(uhd.time_spec())
		self.usrp_sink.set_samp_rate(samp_rate)
		self.usrp_sink.set_center_freq(freq, 0)
		self.usrp_sink.set_gain(tx_gain, 0)
		self.usrp_sink.set_antenna("TX/RX", 0)
		self.tdma_engine = precog.tdma_engine(initial_slot,slot_interval,guard_interval,number_of_slots,lead_limit,link_speed)
		self.gr_multiply_const_vxx_0 = gr.multiply_const_vcc((ampl, ))
		self.gmsk_mod = digital.gmsk_mod(
			samples_per_symbol=samp_per_sym,
			bt=0.35,
			verbose=False,
			log=False,
		)
		self.gmsk_demod = digital.gmsk_demod(
			samples_per_symbol=samp_per_sym,
			gain_mu=0.175,
			mu=0.5,
			omega_relative_limit=0.005,
			freq_error=0.0,
			verbose=False,
			log=False,
		)
		self.extras_pmt_rpc_0 = gr_extras.pmt_rpc(obj=self, result_msg=False)
		self.extras_packet_framer_0 = gr_extras.packet_framer(
		    samples_per_symbol=1,
		    bits_per_symbol=1,
		    access_code="",
		)
		self.extras_packet_deframer_0 = gr_extras.packet_deframer(
		    access_code="",
		    threshold=-1,
		)
		self.burst_gate_0 = precog.burst_gate()

		##################################################
		# Connections
		##################################################
		self.connect((self.usrp_source, 0), (self.tdma_engine, 0))
		self.connect((self.tdma_engine, 0), (self.extras_packet_framer_0, 0))
		self.connect((self.usrp_source, 0), (self.gmsk_demod, 0))
		self.connect((self.gmsk_demod, 0), (self.extras_packet_deframer_0, 0))
		self.connect((self.extras_packet_framer_0, 0), (self.gmsk_mod, 0))
		self.connect((self, 1), (self.tdma_engine, 1))
		self.connect((self, 0), (self.tdma_engine, 3))
		self.connect((self.extras_packet_deframer_0, 0), (self, 1))
		self.connect((self.gmsk_mod, 0), (self.gr_multiply_const_vxx_0, 0))
		self.connect((self.gr_multiply_const_vxx_0, 0), (self.burst_gate_0, 0))
		self.connect((self.burst_gate_0, 0), (self.usrp_sink, 0))
		self.connect((self.extras_packet_deframer_0, 0), (self.tdma_engine, 2))
		self.connect((self, 0), (self.extras_pmt_rpc_0, 0))
		self.connect((self.tdma_engine, 1), (self, 0))

	def get_rx_gain(self):
		return self.rx_gain

	def set_rx_gain(self, rx_gain):
		self.rx_gain = rx_gain
		self.usrp_source.set_gain(self.rx_gain, 0)

	def get_rate(self):
		return self.rate

	def set_rate(self, rate):
		self.rate = rate
		self.set_samp_rate(self.rate)

	def get_samp_per_sym(self):
		return self.samp_per_sym

	def set_samp_per_sym(self, samp_per_sym):
		self.samp_per_sym = samp_per_sym

	def get_args(self):
		return self.args

	def set_args(self, args):
		self.args = args

	def get_freq(self):
		return self.freq

	def set_freq(self, freq):
		self.freq = freq
		self.usrp_sink.set_center_freq(self.freq, 0)
		self.usrp_source.set_center_freq(self.freq, 0)

	def get_ampl(self):
		return self.ampl

	def set_ampl(self, ampl):
		self.ampl = ampl
		self.gr_multiply_const_vxx_0.set_k((self.ampl, ))

	def get_tx_gain(self):
		return self.tx_gain

	def set_tx_gain(self, tx_gain):
		self.tx_gain = tx_gain
		self.usrp_sink.set_gain(self.tx_gain, 0)

	def get_number_of_slots(self):
		return self.number_of_slots

	def set_number_of_slots(self, number_of_slots):
		self.number_of_slots = number_of_slots

	def get_lead_limit(self):
		return self.lead_limit

	def set_lead_limit(self, lead_limit):
		self.lead_limit = lead_limit

	def get_initial_slot(self):
		return self.initial_slot

	def set_initial_slot(self, initial_slot):
		self.initial_slot = initial_slot

	def get_link_speed(self):
		return self.link_speed

	def set_link_speed(self, link_speed):
		self.link_speed = link_speed

	def get_slot_interval(self):
		return self.slot_interval

	def set_slot_interval(self, slot_interval):
		self.slot_interval = slot_interval

	def get_guard_interval(self):
		return self.guard_interval

	def set_guard_interval(self, guard_interval):
		self.guard_interval = guard_interval

	def get_samp_rate(self):
		return self.samp_rate

	def set_samp_rate(self, samp_rate):
		self.samp_rate = samp_rate
		self.usrp_sink.set_samp_rate(self.samp_rate)
		self.usrp_source.set_samp_rate(self.samp_rate)



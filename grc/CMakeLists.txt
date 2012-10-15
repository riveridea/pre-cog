# Copyright 2011-2012 Free Software Foundation, Inc.
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

########################################################################
# Install GRC xml files
########################################################################
list(APPEND grc_sources
    simple_mac.xml
    append_key.xml
    heart_beat.xml
    burst_gate.xml
    channel_access_controller.xml
    tdma_engine.xml
    virtual_channel_formatter.xml
    virtual_channel_mux.xml
    virtual_channel_demux.xml
    fhss_engine_tx.xml
    fhss_engine_rx.xml
    block_tree.xml
    packet_framer.xml
    packet_deframer.xml
    msg_to_stdout.xml
    transition_detect.xml
)

install(
    FILES ${grc_sources}
    DESTINATION ${GRC_BLOCKS_DIR}
    COMPONENT "precog_python"
)

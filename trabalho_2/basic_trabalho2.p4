// SPDX-License-Identifier: Apache-2.0
/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

const bit<8> UDP = 17;
const bit<48> WINDOW_SIZE = 100000;
const bit<5> WINDOW_SHIFT = 17;

const bit<32> RATE_THRESHOLD = 100000;

const bit<32> RECOVERY_THRESHOLD = 12500;
const bit<48> RECOVERY_WINDOWS = 100;

const bit<32> MAX_FLOWS = 8192;

const bit<1> CHANNEL_GREEN = 0;
const bit<1> CHANNEL_RED = 1;

/*************************************************************************
*********************** H E A D E R S  ***********************************
* This program skeleton defines minimal Ethernet and IPv4 headers and    *
* a simple LPM (Longest-Prefix Match) IPv4 forwarding pipeline.          *
* The exercise intentionally leaves TODOs for learners to implement.     *
*************************************************************************/

typedef bit<9>  egressSpec_t;   // Standard BMv2 uses 9 bits for egress_spec
typedef bit<48> macAddr_t;      // Ethernet MAC address
typedef bit<32> ip4Addr_t;      // IPv4 address

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length;
    bit<16> checksum;
}

struct metadata {
    bit<32> flow_hash;
    bit<1>  flow_channel;
    bit<1>  distant_dst;
}

struct headers {
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    udp_t        udp;
}

/*************************************************************************
*********************** P A R S E R  *************************************
* New to P4? A typical parser does this:
*   start -> parse_ethernet
*   parse_ethernet:
*       if etherType == TYPE_IPV4 -> parse_ipv4
*       else accept
*   parse_ipv4 -> accept
* This skeleton leaves the actual states as a TODO to implement later.   *
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition accept;
    }
}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
* High-level intent:
*   - Do an LPM lookup on IPv4 dstAddr
*   - On hit, call ipv4_forward(next-hop MAC, output port)
*   - Otherwise, drop or NoAction (as configured)                         *
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    register<bit<32>>(MAX_FLOWS) flow_byte_count;
    register<bit<48>>(MAX_FLOWS) flow_bucket;
    register<bit<1>>(MAX_FLOWS)  flow_channels;
    register<bit<48>>(MAX_FLOWS) flow_lastcrosses;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;

        if (port == 0) {
            meta.distant_dst = 1;
        } else {
            meta.distant_dst = 0;
        }
    }

    action compute_flow_hash() {
        hash(meta.flow_hash,
            HashAlgorithm.crc32,
            (bit<32>)0,
            {hdr.ipv4.srcAddr,
            hdr.ipv4.dstAddr,
            hdr.udp.srcPort,
            hdr.udp.dstPort,
            hdr.ipv4.protocol},
            MAX_FLOWS);
    }

    action measure_classify() {
        bit<48> last_bucket;
        flow_bucket.read(last_bucket, meta.flow_hash);

        bit<32> accumulated_bytes;
        flow_byte_count.read(accumulated_bytes, meta.flow_hash);

        bit<1> flow_channel;
        flow_channels.read(flow_channel, meta.flow_hash);

        bit<48> flow_lastcross;
        flow_lastcrosses.read(flow_lastcross, meta.flow_hash);

        bit<48> current_bucket = standard_metadata.ingress_global_timestamp >> WINDOW_SHIFT;

        if (current_bucket != last_bucket) {
            bit<32> rate = accumulated_bytes;

            if (flow_channel == CHANNEL_GREEN) {
                if (rate > RATE_THRESHOLD) {
                    flow_channel = CHANNEL_RED;
                    flow_channels.write(meta.flow_hash, flow_channel);

                    flow_lastcross = last_bucket;
                    flow_lastcrosses.write(meta.flow_hash, flow_lastcross);
                }
            } else {
                if (rate > RECOVERY_THRESHOLD) {
                    flow_lastcross = last_bucket;
                    flow_lastcrosses.write(meta.flow_hash, flow_lastcross);
                }

                bit<48> sequence = current_bucket - flow_lastcross - 1;

                if (sequence >= RECOVERY_WINDOWS) {
                    flow_channel = CHANNEL_GREEN;
                    flow_channels.write(meta.flow_hash, flow_channel);
                }
            }

            meta.flow_channel = flow_channel;

            flow_bucket.write(meta.flow_hash, current_bucket);
            flow_byte_count.write(meta.flow_hash, (bit<32>)standard_metadata.packet_length);
        } else {
            accumulated_bytes = accumulated_bytes + (bit<32>)standard_metadata.packet_length;
            flow_byte_count.write(meta.flow_hash, accumulated_bytes);

            flow_channels.read(meta.flow_channel, meta.flow_hash);
        }
    }

    action mark_dscp(bit<6> dscp_value) {
        hdr.ipv4.diffserv = (bit<8>)(dscp_value) << 2;
    }

    table traffic_classification {
        key = {
            meta.flow_channel: exact;
        }
        actions = {
            mark_dscp;
            NoAction;
        }
        size = 2;
        default_action = NoAction();
    }

    table dscp_routing {
        key = {
            hdr.ipv4.diffserv: exact;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 64;
        default_action = NoAction();
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            if (hdr.ipv4.protocol == UDP && hdr.udp.isValid()) {
                compute_flow_hash();

                measure_classify();

                traffic_classification.apply();

                ipv4_lpm.apply();

                if (meta.distant_dst == 1) {
                    dscp_routing.apply();
                }
            } else {
                drop();
            }
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
* Often used for queue marks, mirroring, or post-routing edits.          *
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
* This block shows how to compute IPv4 header checksum when needed.      *
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}


/*************************************************************************
***********************  D E P A R S E R  *******************************
* The deparser serializes headers back onto the packet in order.         *
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
    }
}

/*************************************************************************
***********************  S W I T C H  ***********************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
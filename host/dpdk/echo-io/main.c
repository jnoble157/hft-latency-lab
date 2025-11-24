#include <stdio.h>
#include <stdint.h>
#include <signal.h>
#include <inttypes.h>
#include <stdbool.h>

#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_mbuf.h>
#include <rte_mempool.h>
#include <rte_cycles.h>
#include <rte_ether.h>

#define RX_DESC_DEFAULT 1024
#define TX_DESC_DEFAULT 1024
#define NUM_MBUFS       16384
#define MBUF_CACHE_SIZE 250
#define BURST_SIZE      64

static volatile bool keep_running = true;

static void handle_sigint(int signum) {
    (void)signum;
    keep_running = false;
}

static int init_port(uint16_t port_id, struct rte_mempool *mbuf_pool) {
    struct rte_eth_conf port_conf;
    struct rte_eth_dev_info dev_info;
    int ret;

    rte_eth_dev_info_get(port_id, &dev_info);
    port_conf = (struct rte_eth_conf){0};
    port_conf.rxmode.mq_mode = RTE_ETH_MQ_RX_NONE;
    port_conf.rxmode.offloads = 0;
    port_conf.txmode.mq_mode = RTE_ETH_MQ_TX_NONE;
    port_conf.txmode.offloads = 0;

    ret = rte_eth_dev_configure(port_id, 1, 1, &port_conf);
    if (ret < 0) return ret;

    struct rte_eth_rxconf rx_conf = dev_info.default_rxconf;
    rx_conf.offloads = 0;
    ret = rte_eth_rx_queue_setup(port_id, 0, RX_DESC_DEFAULT,
                                 rte_eth_dev_socket_id(port_id), &rx_conf, mbuf_pool);
    if (ret < 0) return ret;

    struct rte_eth_txconf tx_conf = dev_info.default_txconf;
    tx_conf.offloads = 0;
    ret = rte_eth_tx_queue_setup(port_id, 0, TX_DESC_DEFAULT,
                                 rte_eth_dev_socket_id(port_id), &tx_conf);
    if (ret < 0) return ret;

    ret = rte_eth_dev_start(port_id);
    if (ret < 0) return ret;

    rte_eth_promiscuous_enable(port_id);
    return 0;
}

int main(int argc, char **argv) {
    int ret = rte_eal_init(argc, argv);
    if (ret < 0) {
        rte_exit(EXIT_FAILURE, "EAL init failed\n");
    }

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    uint16_t nb_ports = rte_eth_dev_count_avail();
    if (nb_ports < 2) {
        rte_exit(EXIT_FAILURE, "Need at least 2 ports; found %u\n", nb_ports);
    }

    struct rte_mempool *mbuf_pool = rte_pktmbuf_pool_create(
        "MBUF_POOL", NUM_MBUFS, MBUF_CACHE_SIZE, 0, RTE_MBUF_DEFAULT_BUF_SIZE, rte_socket_id());
    if (mbuf_pool == NULL) {
        rte_exit(EXIT_FAILURE, "Cannot create mbuf pool\n");
    }

    uint16_t port0 = 0, port1 = 1;
    if ((ret = init_port(port0, mbuf_pool)) < 0) {
        rte_exit(EXIT_FAILURE, "Port %u init failed: %d\n", port0, ret);
    }
    if ((ret = init_port(port1, mbuf_pool)) < 0) {
        rte_exit(EXIT_FAILURE, "Port %u init failed: %d\n", port1, ret);
    }

    // Seed a few packets in both directions to kick off io forwarding
    struct rte_ether_addr mac0, mac1;
    rte_eth_macaddr_get(port0, &mac0);
    rte_eth_macaddr_get(port1, &mac1);
    for (int dir = 0; dir < 2; dir++) {
        uint16_t dst_port = dir == 0 ? port1 : port0;
        const struct rte_ether_addr *src_mac = dir == 0 ? &mac0 : &mac1;
        const struct rte_ether_addr *dst_mac = dir == 0 ? &mac1 : &mac0;
        struct rte_mbuf *seed[BURST_SIZE];
        uint16_t n = 0;
        for (; n < BURST_SIZE; n++) {
            struct rte_mbuf *m = rte_pktmbuf_alloc(mbuf_pool);
            if (!m) break;
            // Minimum Ethernet frame payload length without FCS is 60 bytes
            const uint16_t frame_len = RTE_ETHER_MIN_LEN;
            struct rte_ether_hdr *eth = (struct rte_ether_hdr *)rte_pktmbuf_append(m, frame_len);
            if (!eth) { rte_pktmbuf_free(m); break; }
            rte_ether_addr_copy(dst_mac, &eth->dst_addr);
            rte_ether_addr_copy(src_mac, &eth->src_addr);
            eth->ether_type = rte_cpu_to_be_16(RTE_ETHER_TYPE_IPV4);
            seed[n] = m;
        }
        if (n) {
            uint16_t sent = rte_eth_tx_burst(dst_port, 0, seed, n);
            for (uint16_t i = sent; i < n; i++) rte_pktmbuf_free(seed[i]);
        }
    }

    const uint64_t hz = rte_get_timer_hz();
    uint64_t next_stat = rte_get_timer_cycles() + hz;
    uint64_t rx0 = 0, tx0 = 0, rx1 = 0, tx1 = 0, drops = 0;

    struct rte_mbuf *pkts[BURST_SIZE];

    while (keep_running) {
        uint16_t n0 = rte_eth_rx_burst(port0, 0, pkts, BURST_SIZE);
        if (n0) {
            uint16_t sent = rte_eth_tx_burst(port1, 0, pkts, n0);
            for (uint16_t i = sent; i < n0; i++) rte_pktmbuf_free(pkts[i]);
            rx0 += n0; tx1 += sent; drops += (n0 - sent);
        }

        uint16_t n1 = rte_eth_rx_burst(port1, 0, pkts, BURST_SIZE);
        if (n1) {
            uint16_t sent = rte_eth_tx_burst(port0, 0, pkts, n1);
            for (uint16_t i = sent; i < n1; i++) rte_pktmbuf_free(pkts[i]);
            rx1 += n1; tx0 += sent; drops += (n1 - sent);
        }

        uint64_t now = rte_get_timer_cycles();
        if (now >= next_stat) {
            printf("rx0=%" PRIu64 " tx0=%" PRIu64 " rx1=%" PRIu64 " tx1=%" PRIu64 " drops=%" PRIu64 "\n",
                   rx0, tx0, rx1, tx1, drops);
            fflush(stdout);
            next_stat = now + hz;
        }
    }

    rte_eth_dev_stop(port0);
    rte_eth_dev_stop(port1);
    rte_eth_dev_close(port0);
    rte_eth_dev_close(port1);
    return 0;
}



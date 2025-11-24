#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <inttypes.h>
#include <math.h>

#include "../../protocol/lob_v1.h"

static inline uint64_t now_ns_clockid(clockid_t cid) {
    struct timespec ts;
    clock_gettime(cid, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static inline uint64_t htonll_u64(uint64_t x) {
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return ((uint64_t)htonl(x & 0xFFFFFFFFull) << 32) | htonl((uint32_t)(x >> 32));
#else
    return x;
#endif
}
static inline uint64_t ntohll_u64(uint64_t x) { return htonll_u64(x); }

typedef struct {
    uint64_t *buf;
    size_t cap, len;
} vec_u64;

static void vec_init(vec_u64 *v, size_t cap) {
    v->buf = (uint64_t*)malloc(cap * sizeof(uint64_t));
    v->cap = cap; v->len = 0;
}
static void vec_push(vec_u64 *v, uint64_t x) {
    if (v->len < v->cap) v->buf[v->len++] = x;
}
static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t*)a, y = *(const uint64_t*)b;
    return (x > y) - (x < y);
}
static void print_percentiles(vec_u64 *v, const char *unit) {
    if (v->len == 0) { printf("no samples\n"); return; }
    qsort(v->buf, v->len, sizeof(uint64_t), cmp_u64);
    uint64_t p50 = v->buf[(size_t)(0.50 * (v->len-1))];
    uint64_t p99 = v->buf[(size_t)(0.99 * (v->len-1))];
    uint64_t p999= v->buf[(size_t)(0.999* (v->len-1))];
    printf("count=%zu p50=%" PRIu64 "%s p99=%" PRIu64 "%s p999=%" PRIu64 "%s\n",
           v->len, p50, unit, p99, unit, p999, unit);
    v->len = 0; // reset
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage: %s --dst <ip:port> [--bind <ip:port>] [--if <ifname>]\n"
        "          [--mode ping|lob] [--src <messages.csv>] [--price-tick X] [--batch N] [--speed X]\n"
        "          [--pps N] [--count N]\n",
        prog);
    exit(2);
}

static int send_blocking(int fd, const void *buf, size_t len) {
    for (;;) {
        ssize_t m = send(fd, buf, len, 0);
        if (m >= 0) return 0;
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            struct pollfd p = { .fd = fd, .events = POLLOUT };
            (void)poll(&p, 1, 10); // wait up to 10 ms for send buffer space
            continue;
        }
        perror("send");
        return -1;
    }
}

int main(int argc, char **argv) {
    const char *dst = NULL, *bindaddr = "0.0.0.0:0", *ifname = NULL;
    uint64_t pps = 10000, count = 0; // 0=infinite
    const char *mode = "ping"; // or "lob"
    const char *src_path = NULL;
    double price_tick = 0.01;
    int batch = 16;
    double speed = 0.0; // 0 => ignore timestamps, use pps pacing
    const char *dump_features_path = NULL;
    const char *dump_packets_path = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--dst") && i+1 < argc) dst = argv[++i];
        else if (!strcmp(argv[i], "--bind") && i+1 < argc) bindaddr = argv[++i];
        else if (!strcmp(argv[i], "--if") && i+1 < argc) ifname = argv[++i];
        else if (!strcmp(argv[i], "--mode") && i+1 < argc) mode = argv[++i];
        else if (!strcmp(argv[i], "--src") && i+1 < argc) src_path = argv[++i];
        else if (!strcmp(argv[i], "--price-tick") && i+1 < argc) price_tick = atof(argv[++i]);
        else if (!strcmp(argv[i], "--batch") && i+1 < argc) batch = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--speed") && i+1 < argc) speed = atof(argv[++i]);
        else if (!strcmp(argv[i], "--pps") && i+1 < argc) pps = strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--count") && i+1 < argc) count = strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--dump-features") && i+1 < argc) dump_features_path = argv[++i];
        else if (!strcmp(argv[i], "--dump-packets") && i+1 < argc) dump_packets_path = argv[++i];
        else usage(argv[0]);
    }
    if (!dst) usage(argv[0]);

    // Parse ip:port helpers
    char dstbuf[128], bindbuf[128];
    strncpy(dstbuf, dst, sizeof(dstbuf)-1); dstbuf[sizeof(dstbuf)-1]=0;
    strncpy(bindbuf, bindaddr, sizeof(bindbuf)-1); bindbuf[sizeof(bindbuf)-1]=0;
    char *colon = strrchr(dstbuf, ':'); if (!colon) usage(argv[0]);
    *colon = 0; int dstport = atoi(colon+1);
    struct sockaddr_in dstsa = {.sin_family=AF_INET, .sin_port=htons(dstport)};
    if (inet_pton(AF_INET, dstbuf, &dstsa.sin_addr) != 1) usage(argv[0]);
    colon = strrchr(bindbuf, ':'); if (!colon) usage(argv[0]);
    *colon = 0; int bindport = atoi(colon+1);
    struct sockaddr_in bsa = {.sin_family=AF_INET, .sin_port=htons(bindport)};
    if (inet_pton(AF_INET, bindbuf, &bsa.sin_addr) != 1) usage(argv[0]);

    int fd = socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    if (fd < 0) { perror("socket"); return 1; }
    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    if (ifname) {
        setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, ifname, (socklen_t)strlen(ifname)+1);
    }
    if (bind(fd, (struct sockaddr*)&bsa, sizeof(bsa)) < 0) { perror("bind"); return 1; }
    if (connect(fd, (struct sockaddr*)&dstsa, sizeof(dstsa)) < 0) { perror("connect"); return 1; }

    // Choose clock: prefer CLOCK_TAI, else MONOTONIC_RAW
#ifdef CLOCK_TAI
    clockid_t clk = CLOCK_TAI;
#else
    clockid_t clk = CLOCK_MONOTONIC_RAW;
#endif

    // Stats
    vec_u64 rtt_ns; vec_init(&rtt_ns, 200000); // buffer per-interval
    uint64_t sent = 0, received = 0, seq = 0, features_recv = 0;
    int first_features_batch = 1; // mark first DELTAS packet to signal reset
    FILE *dumpf = NULL;
    FILE *dumpp = NULL;
    if (dump_features_path) {
        dumpf = fopen(dump_features_path, "wb");
        if (!dumpf) {
            perror("fopen dump-features");
            // continue without dumping
        }
    }
    if (dump_packets_path) {
        dumpp = fopen(dump_packets_path, "wb");
        if (!dumpp) {
            perror("fopen dump-packets");
            // continue without dumping
        }
    }

    // Rate control
    double interval_ns = pps ? (1e9 / (double)pps) : 0.0;
    uint64_t next_send = now_ns_clockid(clk);
    uint8_t buf[2048];
    struct pollfd pfd = {.fd=fd, .events=POLLIN};

    if (strcmp(mode, "ping") == 0) {
        while (count == 0 || sent < count) {
            // Receive any echos
            for (int k = 0; k < 64; k++) {
                ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, NULL, NULL);
                if (n < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                    perror("recv"); return 1;
                }
                if ((size_t)n >= sizeof(lob_v1_hdr_t)) {
                    uint64_t t_rx = now_ns_clockid(clk);
                    lob_v1_hdr_t *h = (lob_v1_hdr_t*)buf;
                    // Validate FEATURES payload length if present
                    if (h->msg_type == LOB_V1_MSG_FEATURES) {
                        if (n < (ssize_t)(LOB_V1_HDR_LEN + LOB_V1_FEAT_LEN)) {
                            continue;
                        }
                        features_recv++;
                        if (dumpf) {
                            // Write 4B seq (be), 2B count, 8B t_send_ns (be), then 16B features
                            (void)fwrite(&h->seq, 1, sizeof(h->seq), dumpf);
                            uint16_t be_flags;
                            memcpy(&be_flags, &h->flags, sizeof(be_flags));
                            (void)fwrite(&be_flags, 1, sizeof(be_flags), dumpf);
                            (void)fwrite(&h->t_send_ns, 1, sizeof(h->t_send_ns), dumpf);
                            (void)fwrite(buf + LOB_V1_HDR_LEN, 1, LOB_V1_FEAT_LEN, dumpf);
                        }
                    }
                    uint64_t t_send = ntohll_u64(h->t_send_ns);
                    uint64_t rtt = (t_rx >= t_send) ? (t_rx - t_send) : 0;
                    vec_push(&rtt_ns, rtt);
                    received++;
                }
            }

            // Send next if due
            uint64_t now = now_ns_clockid(clk);
            if (!pps || now >= next_send) {
                lob_v1_hdr_t h = {0};
                h.magic[0]='L'; h.magic[1]='O'; h.magic[2]='B'; h.magic[3]='1';
                h.version = 1;
                h.msg_type = LOB_V1_MSG_PING;
                h.flags = htons(0);
                h.hdr_len = htons(LOB_V1_HDR_LEN);
                h.seq = htonl((uint32_t)seq++);
                uint64_t t_send = now_ns_clockid(clk);
                h.t_send_ns = htonll_u64(t_send);
                h.t_ingress_ns = htonll_u64(0);
                h.rsv2 = htons(0);
            if (send_blocking(fd, &h, sizeof(h)) < 0) return 1;
                if (pps) next_send += (uint64_t)interval_ns;
                sent++;
            } else {
                int timeout_ms = (int)((next_send - now) / 1000000ull);
                if (timeout_ms < 0) timeout_ms = 0;
                (void)poll(&pfd, 1, timeout_ms);
            }

            static uint64_t last_print = 0; uint64_t now2 = now_ns_clockid(clk);
            if (last_print == 0) last_print = now2;
            if (now2 - last_print >= 1000000000ull) {
                printf("sent=%" PRIu64 " recv=%" PRIu64 " feat=%" PRIu64 " ", sent, received, features_recv);
                print_percentiles(&rtt_ns, "ns");
                last_print = now2;
            }
        }
    } else if (strcmp(mode, "lob") == 0) {
        if (!src_path) { fprintf(stderr, "--src <messages.csv> required for --mode lob\n"); return 2; }
        FILE *f = fopen(src_path, "r");
        if (!f) { perror("fopen src"); return 1; }

        lob_v1_delta_t *deltas = (lob_v1_delta_t*)malloc(sizeof(lob_v1_delta_t) * (size_t)batch);
        int dn = 0;
        char line[512];
        double first_ts = -1.0;
        uint64_t start_wall = now_ns_clockid(clk);
        uint64_t packet_target_ns = 0;

        while (fgets(line, sizeof(line), f)) {
            // LOBSTER messages: time, type, order_id, size, price, direction
            double t_s = 0.0, price = 0.0; int type = 0, dir = 0; long long order_id = 0; int size = 0;
            if (sscanf(line, "%lf,%d,%lld,%d,%lf,%d", &t_s, &type, &order_id, &size, &price, &dir) != 6) {
                continue;
            }
            if (first_ts < 0.0) first_ts = t_s;

            int side = (dir == 1) ? 0 : 1; // 0=bid,1=ask
            int action = 1; // default add
            int qty = size;
            switch (type) {
                case 1: action = 1; qty = size; break;           // submit -> add
                case 2: action = 2; qty = -size; break;          // cancel -> update (-)
                case 3: action = 2; qty = -size; break;          // execute -> update (-)
                case 4: action = 3; qty = 0; break;              // delete -> remove
                case 5: action = 2; qty = 0; break;              // replace -> update (minimal)
                default: continue;
            }
            int32_t price_ticks_i = (int32_t)llround(price / price_tick);

            lob_v1_delta_t d = {0};
            d.price_ticks = htonl(price_ticks_i);
            d.qty = htonl(qty);
            d.level = htons(0);
            d.side = (uint8_t)side;
            d.action = (uint8_t)action;
            d.reserved = htonl(0);

            // Pace using timestamps if speed>0, else using pps interval
            if (speed > 0.0) {
                uint64_t target_ns = start_wall + (uint64_t)((t_s - first_ts) * (1e9 / speed));
                if (dn == 0) packet_target_ns = target_ns;
                // Wait until scheduled time to send any accumulated batch
                for (;;) {
                    uint64_t noww = now_ns_clockid(clk);
                    // Drain echos while waiting
                    for (int k = 0; k < 64; k++) {
                        ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, NULL, NULL);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                            perror("recv"); return 1;
                        }
                        if ((size_t)n >= sizeof(lob_v1_hdr_t)) {
                            uint64_t t_rx = noww;
                            lob_v1_hdr_t *h = (lob_v1_hdr_t*)buf;
                            if (h->msg_type == LOB_V1_MSG_FEATURES) {
                                if (n < (ssize_t)(LOB_V1_HDR_LEN + LOB_V1_FEAT_LEN)) {
                                    continue;
                                }
                                features_recv++;
                                if (dumpf) {
                                    (void)fwrite(&h->seq, 1, sizeof(h->seq), dumpf);
                                    uint16_t be_flags;
                                    memcpy(&be_flags, &h->flags, sizeof(be_flags));
                                    (void)fwrite(&be_flags, 1, sizeof(be_flags), dumpf);
                                    (void)fwrite(&h->t_send_ns, 1, sizeof(h->t_send_ns), dumpf);
                                    (void)fwrite(buf + LOB_V1_HDR_LEN, 1, LOB_V1_FEAT_LEN, dumpf);
                                }
                            }
                            uint64_t t_send = ntohll_u64(h->t_send_ns);
                            uint64_t rtt = (t_rx >= t_send) ? (t_rx - t_send) : 0;
                            vec_push(&rtt_ns, rtt);
                            received++;
                        }
                    }
                    if (dn >= batch) break;
                    if (noww >= packet_target_ns) break;
                    int timeout_ms = (int)((packet_target_ns - noww) / 1000000ull);
                    if (timeout_ms < 0) timeout_ms = 0;
                    (void)poll(&pfd, 1, timeout_ms);
                }
            }

            // Add delta to batch
            if (dn < batch) deltas[dn++] = d;

            // If batch full, or not using speed and it's time per pps, send
            int should_send = 0;
            if (dn >= batch) should_send = 1;
            if (speed <= 0.0) {
                uint64_t noww = now_ns_clockid(clk);
                if (!pps || noww >= next_send) should_send = (dn > 0);
            } else {
                uint64_t noww = now_ns_clockid(clk);
                if (noww >= packet_target_ns && dn > 0) should_send = 1;
            }

            if (should_send) {
                lob_v1_hdr_t h = {0};
                h.magic[0]='L'; h.magic[1]='O'; h.magic[2]='B'; h.magic[3]='1';
                h.version = 1;
                h.msg_type = LOB_V1_MSG_DELTAS;
                uint16_t fcnt = (uint16_t)dn;
                if (first_features_batch) { fcnt |= 0x8000; first_features_batch = 0; }
                h.flags = htons(fcnt); // high bit: reset, low 15: count
                h.hdr_len = htons(LOB_V1_HDR_LEN);
                h.seq = htonl((uint32_t)seq++);
                uint64_t t_send = now_ns_clockid(clk);
                h.t_send_ns = htonll_u64(t_send);
                h.t_ingress_ns = htonll_u64(0);
                h.rsv2 = htons(0);

                size_t pkt_len = sizeof(lob_v1_hdr_t) + (size_t)dn * sizeof(lob_v1_delta_t);
                uint8_t *pkt = (uint8_t*)malloc(pkt_len);
                memcpy(pkt, &h, sizeof(h));
                memcpy(pkt + sizeof(h), deltas, (size_t)dn * sizeof(lob_v1_delta_t));
                // Optional: dump exact packet deltas for later validation
                if (dumpp) {
                    // Write 4B seq (be), 2B count, then raw on-wire deltas
                    (void)fwrite(&h.seq, 1, sizeof(h.seq), dumpp);
                    uint16_t be_cnt = htons((uint16_t)dn);
                    (void)fwrite(&be_cnt, 1, sizeof(be_cnt), dumpp);
                    (void)fwrite(deltas, 1, (size_t)dn * sizeof(lob_v1_delta_t), dumpp);
                }
                if (send_blocking(fd, pkt, pkt_len) < 0) { free(pkt); fclose(f); return 1; }
                free(pkt);
                if (pps && speed <= 0.0) next_send += (uint64_t)interval_ns;
                sent++;
                dn = 0; packet_target_ns = 0;

                // Post-send quick drain: poll a few times briefly to catch replies
                // This ensures we still count FEATURES even when running at higher speeds.
                for (int tries = 0; tries < 5; ++tries) {
                    struct pollfd p2 = {.fd = fd, .events = POLLIN};
                    int pr = poll(&p2, 1, 2); // ~2ms
                    if (pr > 0 && (p2.revents & POLLIN)) {
                        ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, NULL, NULL);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                            // Do not abort the whole run; just stop draining on error
                            break;
                        }
                        if ((size_t)n >= sizeof(lob_v1_hdr_t)) {
                            lob_v1_hdr_t *rh = (lob_v1_hdr_t*)buf;
                            if (rh->msg_type == LOB_V1_MSG_FEATURES) {
                                if ((size_t)n >= (sizeof(lob_v1_hdr_t) + LOB_V1_FEAT_LEN)) {
                                    features_recv++;
                                    if (dumpf) {
                                        (void)fwrite(&rh->seq, 1, sizeof(rh->seq), dumpf);
                                        uint16_t be_flags; memcpy(&be_flags, &rh->flags, sizeof(be_flags));
                                        (void)fwrite(&be_flags, 1, sizeof(be_flags), dumpf);
                                        (void)fwrite(&rh->t_send_ns, 1, sizeof(rh->t_send_ns), dumpf);
                                        (void)fwrite(buf + sizeof(lob_v1_hdr_t), 1, LOB_V1_FEAT_LEN, dumpf);
                                    }
                                }
                            } else {
                                received++;
                            }
                        }
                    } else {
                        break;
                    }
                }

                // Print stats every ~1s
                static uint64_t last_print2 = 0; uint64_t now2 = now_ns_clockid(clk);
                if (last_print2 == 0) last_print2 = now2;
                if (now2 - last_print2 >= 1000000000ull) {
                    printf("sent=%" PRIu64 " recv=%" PRIu64 " feat=%" PRIu64 " ", sent, received, features_recv);
                    print_percentiles(&rtt_ns, "ns");
                    last_print2 = now2;
                }
            }
        }

        // Flush remaining
        if (dn > 0) {
            lob_v1_hdr_t h = {0};
            h.magic[0]='L'; h.magic[1]='O'; h.magic[2]='B'; h.magic[3]='1';
            h.version = 1;
            h.msg_type = LOB_V1_MSG_DELTAS;
            uint16_t fcnt2 = (uint16_t)dn;
            if (first_features_batch) { fcnt2 |= 0x8000; first_features_batch = 0; }
            h.flags = htons(fcnt2);
            h.hdr_len = htons(LOB_V1_HDR_LEN);
            h.seq = htonl((uint32_t)seq++);
            uint64_t t_send = now_ns_clockid(clk);
            h.t_send_ns = htonll_u64(t_send);
            h.t_ingress_ns = htonll_u64(0);
            h.rsv2 = htons(0);
            size_t pkt_len = sizeof(lob_v1_hdr_t) + (size_t)dn * sizeof(lob_v1_delta_t);
            uint8_t *pkt = (uint8_t*)malloc(pkt_len);
            memcpy(pkt, &h, sizeof(h));
            memcpy(pkt + sizeof(h), deltas, (size_t)dn * sizeof(lob_v1_delta_t));
            (void)send(fd, pkt, pkt_len, 0);
            free(pkt);
            sent++;
        }

        fclose(f);
    } else {
        fprintf(stderr, "Unknown --mode %s\n", mode); return 2;
    }

    // Drain remaining replies for a short grace period
    uint64_t end = now_ns_clockid(clk) + 200000000ull;
    while (now_ns_clockid(clk) < end) {
        ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, NULL, NULL);
        if (n <= 0) break;
        received++;
    }
    printf("Final: sent=%" PRIu64 " recv=%" PRIu64 " feat=%" PRIu64 "\n", sent, received, features_recv);
    if (rtt_ns.len) { print_percentiles(&rtt_ns, "ns"); }
    if (dumpf) fclose(dumpf);
    if (dumpp) fclose(dumpp);
    return 0;
}



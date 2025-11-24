#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

// Header layout (big-endian): 32 bytes total
//  0: magic[4]          "LOB1"
//  4: version[1]
//  5: msg_type[1]
//  6: flags[2]
//  8: hdr_len[2]
// 10: seq[4]
// 14: t_send_ns[8]
// 22: t_ingress_ns[8]   <-- we fill this
// 30: rsv2[2]

static inline uint64_t now_ns(void) {
#ifdef CLOCK_TAI
    struct timespec ts;
    if (clock_gettime(CLOCK_TAI, &ts) == 0) {
        return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
    }
#endif
    struct timespec ts2;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts2);
    return (uint64_t)ts2.tv_sec * 1000000000ull + (uint64_t)ts2.tv_nsec;
}

static inline uint64_t htonll_u64(uint64_t x) {
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return ((uint64_t)htonl((uint32_t)(x & 0xffffffffull)) << 32) | htonl((uint32_t)(x >> 32));
#else
    return x;
#endif
}

int main(int argc, char **argv) {
    const char *bind_ip = "0.0.0.0";
    int port = 4000;
    if (argc == 2) {
        const char *arg = argv[1];
        const char *colon = strrchr(arg, ':');
        if (colon) {
            char tmp[64];
            size_t n = (size_t)(colon - arg);
            if (n >= sizeof(tmp)) n = sizeof(tmp) - 1;
            memcpy(tmp, arg, n); tmp[n] = '\0';
            bind_ip = strdup(tmp);
            port = atoi(colon + 1);
        } else {
            port = atoi(arg);
        }
    }

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }

    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

    struct sockaddr_in sa = {0};
    sa.sin_family = AF_INET;
    sa.sin_port = htons(port);
    if (inet_pton(AF_INET, bind_ip, &sa.sin_addr) != 1) {
        fprintf(stderr, "bad bind ip: %s\n", bind_ip);
        return 2;
    }
    if (bind(fd, (struct sockaddr*)&sa, sizeof(sa)) < 0) { perror("bind"); return 1; }

    // Optional: try to set real-time priority best-effort
    struct sched_param sp = { .sched_priority = 70 };
    sched_setscheduler(0, SCHED_FIFO, &sp);

    uint8_t buf[2048];
    for (;;) {
        struct sockaddr_in peer;
        socklen_t plen = sizeof(peer);
        ssize_t n = recvfrom(fd, buf, sizeof(buf), 0, (struct sockaddr*)&peer, &plen);
        if (n < 0) {
            if (errno == EINTR) continue;
            perror("recvfrom");
            continue;
        }
        if (n >= 32 && buf[0]=='L' && buf[1]=='O' && buf[2]=='B' && buf[3]=='1') {
            uint64_t t_ing = now_ns();
            uint64_t be = htonll_u64(t_ing);
            // write at offset 22 (t_ingress_ns)
            memcpy(buf + 22, &be, sizeof(be));
        }
        (void)sendto(fd, buf, (size_t)n, 0, (struct sockaddr*)&peer, plen);
    }
}



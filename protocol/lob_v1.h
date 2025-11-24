#pragma once
#include <stdint.h>

#if defined(__APPLE__)
#  include <libkern/OSByteOrder.h>
#  define htobe64(x) OSSwapHostToBigInt64(x)
#  define be64toh(x) OSSwapBigToHostInt64(x)
#elif !defined(htobe64)
#  include <endian.h>
#endif

#pragma pack(push, 1)
typedef struct {
    uint8_t  magic[4];      // 'L','O','B','1'
    uint8_t  version;       // 0x01
    uint8_t  msg_type;      // 0=ping, 1=lob_deltas, 2=features
    uint16_t flags;         // DELTAS: bit15=reset, bits[14:0]=delta_count; FEATURES: echoed from request
    uint16_t hdr_len;       // 32
    uint32_t seq;           // be32
    uint64_t t_send_ns;     // be64
    uint64_t t_ingress_ns;  // be64 (set by echo)
    uint16_t rsv2;          // 0
} lob_v1_hdr_t;

typedef struct {
    int32_t  price_ticks;   // be32
    int32_t  qty;           // be32
    uint16_t level;         // be16
    uint8_t  side;          // 0=bid,1=ask
    uint8_t  action;        // 0=set,1=add,2=update,3=remove
    uint32_t reserved;      // 0
} lob_v1_delta_t;
#pragma pack(pop)

// 16B feature snapshot payload (network byte order for fields)
#pragma pack(push, 1)
typedef struct {
    int32_t  ofi_q32;        // signed Q32.0
    int16_t  tob_imb_q1_15;  // signed Q1.15
    uint16_t rsv0;           // padding
    uint32_t burst_q16_16;   // unsigned Q16.16
    uint32_t vol_q16_16;     // unsigned Q16.16
} lob_v1_feat_t;
#pragma pack(pop)

enum { LOB_V1_HDR_LEN = 32, LOB_V1_DELTA_LEN = 16, LOB_V1_FEAT_LEN = 16 };
// Extended feature+score payload appends a 32-bit score (Q16.16)
#pragma pack(push, 1)
typedef struct {
    int32_t  ofi_q32;        // signed Q32.0
    int16_t  tob_imb_q1_15;  // signed Q1.15
    uint16_t rsv0;           // padding
    uint32_t burst_q16_16;   // unsigned Q16.16
    uint32_t vol_q16_16;     // unsigned Q16.16
    uint32_t score_q16_16;   // signed/unsigned Q16.16 model score (extension)
} lob_v1_feat_score_t;
#pragma pack(pop)

enum { LOB_V1_FEAT_SCORE_LEN = 20 };

// Timing metadata trailer (40 bytes) - appended to FEATURES_WITH_TIMING response
#pragma pack(push, 1)
typedef struct {
    uint64_t t2_rx_ns;       // PYNQ RX timestamp (after recvfrom)
    uint64_t t3_dma_start_ns; // DMA initiation timestamp
    uint64_t t4_feat_done_ns; // Feature DMA complete timestamp
    uint64_t t5_score_done_ns; // Score DMA complete timestamp
    uint64_t t6_tx_ns;        // PYNQ TX timestamp (before sendto)
} lob_v1_timing_t;
#pragma pack(pop)

enum { LOB_V1_TIMING_LEN = 40 };
enum { LOB_V1_MSG_PING = 0, LOB_V1_MSG_DELTAS = 1, LOB_V1_MSG_FEATURES = 2, LOB_V1_MSG_FEAT_SCORE = 3, LOB_V1_MSG_FEATURES_WITH_TIMING = 4 };
// Flags for DELTAS
enum { LOB_V1_FLAG_RESET = 1u << 15 };
enum { LOB_V1_FLAGS_COUNT_MASK = 0x7FFFu };


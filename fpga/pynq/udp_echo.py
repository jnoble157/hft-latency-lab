#!/usr/bin/env python3
import argparse, socket, struct, time

HDR_FMT = ">4sBBHHIQQH"  # magic,ver,type,flags,hdr_len,seq,t_send_ns,t_ingress_ns,rsv2
HDR_LEN = 32

def now_ns():
    if hasattr(time, "CLOCK_TAI"):
        try:
            return time.clock_gettime_ns(time.CLOCK_TAI)
        except Exception:
            pass
    try:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    except Exception:
        return time.time_ns()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0:4000")
    args = ap.parse_args()
    host, port = args.bind.rsplit(":", 1)
    port = int(port)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))

    while True:
        data, addr = s.recvfrom(2048)
        if len(data) < HDR_LEN:
            continue
        t_ing = now_ns()
        fields = list(struct.unpack(HDR_FMT, data[:HDR_LEN]))
        if fields[0] != b"LOB1":
            continue
        fields[7] = t_ing  # set t_ingress_ns
        out = struct.pack(HDR_FMT, *fields)
        s.sendto(out + data[HDR_LEN:], addr)

if __name__ == "__main__":
    main()



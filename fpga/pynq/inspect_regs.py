#!/usr/bin/env python3
import sys
from pynq import Overlay, MMIO

def main():
    ol = Overlay("/home/xilinx/feature_overlay.bit")
    
    print("\n=== IP Dictionary ===")
    for name, ip in ol.ip_dict.items():
        print(f"{name}:")
        if 'phys_addr' in ip:
            print(f"  phys_addr: 0x{ip['phys_addr']:x}")
        if 'mem' in ip:
            for mname, m in ip['mem'].items():
                print(f"  mem['{mname}']: 0x{m['phys_addr']:x}")
    
    print("\n=== Checking DMAs ===")
    # Check axi_dma_0 and axi_dma_1 specifically
    for dma_name in ["axi_dma_0", "axi_dma_1"]:
        if dma_name in ol.ip_dict:
            addr = ol.ip_dict[dma_name]['phys_addr']
            print(f"\nChecking {dma_name} at 0x{addr:x}")
            try:
                mmio = MMIO(addr, 65536)
                # Read MM2S Control(0x00)/Status(0x04) and S2MM Control(0x30)/Status(0x34)
                mm2s_cr = mmio.read(0x00)
                mm2s_sr = mmio.read(0x04)
                s2mm_cr = mmio.read(0x30)
                s2mm_sr = mmio.read(0x34)
                print(f"  MM2S_CR (0x00): 0x{mm2s_cr:08x}")
                print(f"  MM2S_SR (0x04): 0x{mm2s_sr:08x}")
                print(f"  S2MM_CR (0x30): 0x{s2mm_cr:08x}")
                print(f"  S2MM_SR (0x34): 0x{s2mm_sr:08x}")
            except Exception as e:
                print(f"  Error reading DMA: {e}")
        else:
            print(f"{dma_name} NOT FOUND in ip_dict")

if __name__ == "__main__":
    main()

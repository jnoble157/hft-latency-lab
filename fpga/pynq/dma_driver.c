#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <stdint.h>
#include <unistd.h>

// Register Offsets for AXI DMA
#define MM2S_DMACR 0x00
#define MM2S_DMASR 0x04
#define MM2S_SA    0x18
#define MM2S_LENGTH 0x28

#define S2MM_DMACR 0x30
#define S2MM_DMASR 0x34
#define S2MM_DA    0x48
#define S2MM_LENGTH 0x58

// Globals
static int mem_fd = -1;

// Helper to write 32-bit register
static inline void reg_write(void *base, uint32_t offset, uint32_t value) {
    *((volatile uint32_t *)((char*)base + offset)) = value;
}

static inline uint32_t reg_read(void *base, uint32_t offset) {
    return *((volatile uint32_t *)((char*)base + offset));
}

// Initialize /dev/mem (call once)
int dma_init() {
    if (mem_fd >= 0) return 0;
    mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem_fd < 0) {
        perror("dma_init: open /dev/mem");
        return -1;
    }
    return 0;
}

// Map a specific DMA controller (returns pointer to base)
void* map_dma(uint32_t phys_addr) {
    if (mem_fd < 0) dma_init();
    
    uint32_t page_size = sysconf(_SC_PAGESIZE);
    uint32_t map_base = phys_addr & ~(page_size - 1);
    uint32_t offset = phys_addr - map_base;
    
    // Map 64KB to cover register space
    void *mapped_base = mmap(NULL, 65536, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, map_base);
    if (mapped_base == MAP_FAILED) {
        perror("map_dma");
        return NULL;
    }
    
    return (void*)((char*)mapped_base + offset);
}

// Unmap
void unmap_dma(void *virt_addr) {
    // Note: This calculates base incorrectly if we don't track it, 
    // but for this simple script we rely on OS cleanup on exit usually.
    // Proper unmap requires original pointer from mmap. 
    // For HFT loop, we never unmap.
}

// Start MM2S (Host -> FPGA)
void dma_start_mm2s(void *dma_base, uint32_t src_phys, uint32_t length) {
    reg_write(dma_base, MM2S_DMACR, 0x0001); // RS=1
    reg_write(dma_base, MM2S_SA, src_phys);
    reg_write(dma_base, MM2S_LENGTH, length);
}

// Start S2MM (FPGA -> Host)
void dma_start_s2mm(void *dma_base, uint32_t dst_phys, uint32_t length) {
    reg_write(dma_base, S2MM_DMACR, 0x0001); // RS=1
    reg_write(dma_base, S2MM_DA, dst_phys);
    reg_write(dma_base, S2MM_LENGTH, length);
}

// Wait for S2MM completion (Blocking tight loop - Fast!)
// Returns 0 on success, -1 on error
int dma_wait_s2mm(void *dma_base) {
    volatile uint32_t *sr = (volatile uint32_t *)((char*)dma_base + S2MM_DMASR);
    
    // Timeout safety (approx loop count, not precise time)
    // ARM ~667MHz. 1M loops is plenty for 1us operation.
    for (int i = 0; i < 1000000; i++) {
        uint32_t val = *sr;
        
        if (val & 0x1000) { // IOC (Bit 12) set
             reg_write(dma_base, S2MM_DMASR, 0x1000); // Clear IOC
             return 0; 
        }
        
        if (val & 0x70) { // DMADecErr, DMASlvErr, DMAIntErr
            return -1;
        }
    }
    return -2; // Timeout
}

// Start AND Wait for Score (Special case for draining MLP)
// Returns 0 on success, -1 on error, -2 timeout
int dma_drain_score(void *dma_score_base, uint32_t dst_phys) {
    reg_write(dma_score_base, S2MM_DMACR, 0x0001);
    reg_write(dma_score_base, S2MM_DA, dst_phys);
    reg_write(dma_score_base, S2MM_LENGTH, 4); // Always 4 bytes
    
    return dma_wait_s2mm(dma_score_base);
}


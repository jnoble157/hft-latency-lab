
import json
import numpy as np
import struct

def main():
    with open("mlp_int8.json") as f:
        j = json.load(f)

    # Inputs from our debug log: ofi=18, imb=32767, others=0
    # The Feature block outputs these as 16 bytes:
    # int32 ofi, int16 imb, uint16 rsv, uint32 burst, uint32 vol
    # But MLP likely takes them as raw int8/int16/int32 inputs.
    # Let's simulate the Q16.16 pipeline flow if possible, or just the matrix math.
    
    # Model weights
    w0 = np.array(j['w0_int8'])
    b0 = np.array(j['b0_int32'])
    w1 = np.array(j['w1_int8'])
    b1 = np.array(j['b1_int32'])
    
    # Scales (simplified model of what HLS might be doing)
    # HLS usually does: (Input * InScale * W + Bias) -> Quantize
    # But here we have explicit scales.
    # Let's just do a naive int dot product first to see if it's even capable of non-zero.
    
    # Input vector X (approximate based on feature echo logs)
    # OFI=18, IMB=32767. The others are 0.
    # NOTE: If the model expects normalized inputs, 18 might be "tiny".
    x = np.array([18, 32767, 0, 0]) # Assuming 4 inputs? JSON norm suggests 4 inputs.
    
    print(f"Input X: {x}")
    
    # Layer 0
    # y0 = x @ w0 + b0
    # Weights are [InputDim x HiddenDim] or [HiddenDim x InputDim]?
    # JSON w0_int8 has 32 entries, each length 4. So [32, 4].
    # We need x to be [4].
    
    y0 = np.dot(w0, x) + b0
    print(f"L0 pre-activation (int): {y0}")
    
    # ReLU
    y0_relu = np.maximum(y0, 0)
    print(f"L0 post-ReLU (int): {y0_relu}")
    
    # Layer 1
    # y1 = y0_relu @ w1 + b1
    # w1 is [1, 32]
    y1 = np.dot(w1, y0_relu) + b1
    print(f"L1 output (int): {y1}")
    
    # Scale check
    # If scales are tiny, maybe the final Q16.16 export flushes to 0?
    
if __name__ == "__main__":
    main()


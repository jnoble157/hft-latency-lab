#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple

import numpy as np


def clamp_int(x: np.ndarray, min_v: int, max_v: int) -> np.ndarray:
    return np.minimum(np.maximum(x, min_v), max_v)


@dataclass
class QuantTensor:
    data: np.ndarray  # integer tensor
    scale: float      # real scale (per-tensor symmetric)
    zero_point: int   # always 0 for symmetric


def quantize_symmetric(x: np.ndarray, num_bits: int = 8, max_abs: float = None) -> QuantTensor:
    """
    Quantize float tensor to signed int with symmetric range (zero_point=0).
    Returns integer tensor and scale where x_q ≈ x / scale.
    """
    qmin = -(2 ** (num_bits - 1))
    qmax = (2 ** (num_bits - 1)) - 1
    if max_abs is None:
        max_abs = float(np.max(np.abs(x))) + 1e-12
    scale = max_abs / qmax if max_abs > 0 else 1.0
    x_q = np.round(x / scale).astype(np.int64)
    x_q = clamp_int(x_q, qmin, qmax).astype(np.int32)
    return QuantTensor(data=x_q, scale=scale, zero_point=0)


def dequantize(q: QuantTensor) -> np.ndarray:
    return q.data.astype(np.float32) * q.scale


def quantize_bias(bias: np.ndarray, input_scale: float, weight_scale: float) -> Tuple[np.ndarray, float]:
    """
    Bias is accumulated in the same scale as (input_scale * weight_scale).
    Returns (bias_int32, bias_scale) where bias_int32 ≈ bias / bias_scale, bias_scale = input_scale * weight_scale.
    """
    bias_scale = input_scale * weight_scale
    b_q = np.round(bias / bias_scale).astype(np.int64)
    b_q = clamp_int(b_q, -(2**31), (2**31) - 1).astype(np.int32)
    return b_q, bias_scale


def linear_int8_emulate(
    x_q: QuantTensor,
    w_q: QuantTensor,
    b_q: np.ndarray,
    bias_scale: float,
    out_bits: int = 16,
) -> Tuple[QuantTensor, float]:
    """
    Emulate y = x @ W^T + b with integer arithmetic:
      acc_int32 = Σ (x_i * w_i) + b_int32
      y_float ≈ acc_int32 * (x_scale * w_scale)
    Then requantize to out_bits signed integer with symmetric scaling.
    """
    assert x_q.zero_point == 0 and w_q.zero_point == 0
    # Matmul in int32
    acc = (x_q.data.astype(np.int32) @ w_q.data.T.astype(np.int32)).astype(np.int64)
    # Add bias (int32) broadcast
    if b_q is not None:
        acc = acc + b_q.astype(np.int64)
    # Convert to float with combined scale
    y_f = acc.astype(np.float64) * (x_q.scale * w_q.scale)  # + b_q*bias_scale folded above
    # Requantize to out_bits symmetric
    y_q = quantize_symmetric(y_f.astype(np.float32), num_bits=out_bits)
    return y_q, y_q.scale


def make_int8_linear_from_fp32(
    x: np.ndarray,
    W: np.ndarray,
    b: np.ndarray,
    x_bits: int = 8,
    w_bits: int = 8,
    out_bits: int = 16,
) -> Tuple[QuantTensor, QuantTensor, np.ndarray, float]:
    """
    Given representative inputs x (for calibration), and fp32 weights/bias,
    produce quantized tensors and return (x_q, w_q, b_q, bias_scale).
    """
    # Calibrate input scale using sample
    x_q = quantize_symmetric(x, num_bits=x_bits)
    # Calibrate weight scale per-tensor
    w_q = quantize_symmetric(W, num_bits=w_bits)
    # Bias in combined scale
    b_q, bias_scale = quantize_bias(b, x_q.scale, w_q.scale)
    return x_q, w_q, b_q, bias_scale



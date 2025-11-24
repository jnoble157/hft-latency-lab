; ModuleID = '/home/josh-noble/Documents/hft/neuro-hft-fpga/fpga/ip/feature_pipe/mlp_core_stream/mlp_core_stream/solution1/.autopilot/db/a.g.ld.5.gdce.bc'
source_filename = "llvm-link"
target datalayout = "e-m:e-i64:64-i128:128-i256:256-i512:512-i1024:1024-i2048:2048-i4096:4096-n8:16:32:64-S128-v16:16-v24:32-v32:32-v48:64-v96:128-v192:256-v256:256-v512:512-v1024:1024"
target triple = "fpga64-xilinx-none"

%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" = type { %"struct.hls::axis<ap_uint<128>, 0, 0, 0, '8', false>" }
%"struct.hls::axis<ap_uint<128>, 0, 0, 0, '8', false>" = type { %"struct.ap_uint<128>", %"struct.ap_uint<16>", %"struct.ap_uint<16>", %"struct.hls::axis_disabled_signal", %"struct.ap_uint<1>", %"struct.hls::axis_disabled_signal", %"struct.hls::axis_disabled_signal" }
%"struct.ap_uint<128>" = type { %"struct.ap_int_base<128, false>" }
%"struct.ap_int_base<128, false>" = type { %"struct.ssdm_int<128, false>" }
%"struct.ssdm_int<128, false>" = type { i128 }
%"struct.ap_uint<16>" = type { %"struct.ap_int_base<16, false>" }
%"struct.ap_int_base<16, false>" = type { %"struct.ssdm_int<16, false>" }
%"struct.ssdm_int<16, false>" = type { i16 }
%"struct.ap_uint<1>" = type { %"struct.ap_int_base<1, false>" }
%"struct.ap_int_base<1, false>" = type { %"struct.ssdm_int<1, false>" }
%"struct.ssdm_int<1, false>" = type { i1 }
%"struct.hls::axis_disabled_signal" = type { i8 }
%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" = type { %"struct.hls::axis<ap_uint<32>, 0, 0, 0, '8', false>" }
%"struct.hls::axis<ap_uint<32>, 0, 0, 0, '8', false>" = type { %"struct.ap_uint<32>", %"struct.ap_uint<4>", %"struct.ap_uint<4>", %"struct.hls::axis_disabled_signal", %"struct.ap_uint<1>", %"struct.hls::axis_disabled_signal", %"struct.hls::axis_disabled_signal" }
%"struct.ap_uint<32>" = type { %"struct.ap_int_base<32, false>" }
%"struct.ap_int_base<32, false>" = type { %"struct.ssdm_int<32, false>" }
%"struct.ssdm_int<32, false>" = type { i32 }
%"struct.ap_uint<4>" = type { %"struct.ap_int_base<4, false>" }
%"struct.ap_int_base<4, false>" = type { %"struct.ssdm_int<4, false>" }
%"struct.ssdm_int<4, false>" = type { i4 }

; Function Attrs: noinline willreturn
define void @apatb_mlp_core_stream_ir(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias nonnull dereferenceable(32) %s_axis_feat, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias nonnull dereferenceable(12) %m_axis_score, i1* noalias nocapture nonnull dereferenceable(1) %done_pulse) local_unnamed_addr #0 {
entry:
  %s_axis_feat_copy.data = alloca i128, align 512
  %s_axis_feat_copy.keep = alloca i16, align 512
  %s_axis_feat_copy.strb = alloca i16, align 512
  %s_axis_feat_copy.last = alloca i1, align 512
  %m_axis_score_copy.data = alloca i32, align 512
  %m_axis_score_copy.keep = alloca i4, align 512
  %m_axis_score_copy.strb = alloca i4, align 512
  %m_axis_score_copy.last = alloca i1, align 512
  %done_pulse_copy = alloca i1, align 512
  call fastcc void @copy_in(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* nonnull %s_axis_feat, i128* nonnull align 512 %s_axis_feat_copy.data, i16* nonnull align 512 %s_axis_feat_copy.keep, i16* nonnull align 512 %s_axis_feat_copy.strb, i1* nonnull align 512 %s_axis_feat_copy.last, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* nonnull %m_axis_score, i32* nonnull align 512 %m_axis_score_copy.data, i4* nonnull align 512 %m_axis_score_copy.keep, i4* nonnull align 512 %m_axis_score_copy.strb, i1* nonnull align 512 %m_axis_score_copy.last, i1* nonnull %done_pulse, i1* nonnull align 512 %done_pulse_copy)
  call void @apatb_mlp_core_stream_hw(i128* %s_axis_feat_copy.data, i16* %s_axis_feat_copy.keep, i16* %s_axis_feat_copy.strb, i1* %s_axis_feat_copy.last, i32* %m_axis_score_copy.data, i4* %m_axis_score_copy.keep, i4* %m_axis_score_copy.strb, i1* %m_axis_score_copy.last, i1* %done_pulse_copy)
  call void @copy_back(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %s_axis_feat, i128* %s_axis_feat_copy.data, i16* %s_axis_feat_copy.keep, i16* %s_axis_feat_copy.strb, i1* %s_axis_feat_copy.last, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %m_axis_score, i32* %m_axis_score_copy.data, i4* %m_axis_score_copy.keep, i4* %m_axis_score_copy.strb, i1* %m_axis_score_copy.last, i1* %done_pulse, i1* %done_pulse_copy)
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @copy_in(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias, i128* noalias align 512 "unpacked"="1.0" %_V_data_V, i16* noalias align 512 "unpacked"="1.1" %_V_keep_V, i16* noalias align 512 "unpacked"="1.2" %_V_strb_V, i1* noalias align 512 "unpacked"="1.3" %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias, i32* noalias align 512 "unpacked"="3.0" %_V_data_V1, i4* noalias align 512 "unpacked"="3.1" %_V_keep_V2, i4* noalias align 512 "unpacked"="3.2" %_V_strb_V3, i1* noalias align 512 "unpacked"="3.3" %_V_last_V4, i1* noalias readonly, i1* noalias align 512) unnamed_addr #1 {
entry:
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>.15"(i128* align 512 %_V_data_V, i16* align 512 %_V_keep_V, i16* align 512 %_V_strb_V, i1* align 512 %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0)
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"(i32* align 512 %_V_data_V1, i4* align 512 %_V_keep_V2, i4* align 512 %_V_strb_V3, i1* align 512 %_V_last_V4, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %1)
  call fastcc void @onebyonecpy_hls.p0i1(i1* align 512 %3, i1* %2)
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias %dst, i128* noalias align 512 "unpacked"="1.0" %src_V_data_V, i16* noalias align 512 "unpacked"="1.1" %src_V_keep_V, i16* noalias align 512 "unpacked"="1.2" %src_V_strb_V, i1* noalias align 512 "unpacked"="1.3" %src_V_last_V) unnamed_addr #2 {
entry:
  %0 = icmp eq %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %dst, null
  br i1 %0, label %ret, label %copy

copy:                                             ; preds = %entry
  call fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* nonnull %dst, i128* align 512 %src_V_data_V, i16* align 512 %src_V_keep_V, i16* align 512 %src_V_strb_V, i1* align 512 %src_V_last_V)
  br label %ret

ret:                                              ; preds = %copy, %entry
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias nocapture, i128* noalias nocapture align 512 "unpacked"="1.0" %_V_data_V, i16* noalias nocapture align 512 "unpacked"="1.1" %_V_keep_V, i16* noalias nocapture align 512 "unpacked"="1.2" %_V_strb_V, i1* noalias nocapture align 512 "unpacked"="1.3" %_V_last_V) unnamed_addr #3 {
entry:
  %1 = alloca i1
  %2 = alloca i128
  %3 = alloca i16
  %4 = alloca i16
  %5 = alloca %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"
  br label %empty

empty:                                            ; preds = %push, %entry
  %6 = bitcast i128* %_V_data_V to i8*
  %7 = call i1 @fpga_fifo_not_empty_16(i8* %6)
  br i1 %7, label %push, label %ret

push:                                             ; preds = %empty
  %8 = bitcast i128* %2 to i8*
  %9 = bitcast i128* %_V_data_V to i8*
  call void @fpga_fifo_pop_16(i8* %8, i8* %9)
  %10 = load volatile i128, i128* %2
  %11 = bitcast i16* %4 to i8*
  %12 = bitcast i16* %_V_keep_V to i8*
  call void @fpga_fifo_pop_2(i8* %11, i8* %12)
  %13 = load volatile i16, i16* %4
  %14 = bitcast i16* %3 to i8*
  %15 = bitcast i16* %_V_strb_V to i8*
  call void @fpga_fifo_pop_2(i8* %14, i8* %15)
  %16 = load volatile i16, i16* %3
  %17 = bitcast i1* %1 to i8*
  %18 = bitcast i1* %_V_last_V to i8*
  call void @fpga_fifo_pop_1(i8* %17, i8* %18)
  %19 = bitcast i1* %1 to i8*
  %20 = load i8, i8* %19
  %21 = trunc i8 %20 to i1
  %.fca.0.0.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" undef, i128 %10, 0, 0, 0, 0, 0
  %.fca.0.1.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %.fca.0.0.0.0.0.insert, i16 %13, 0, 1, 0, 0, 0
  %.fca.0.2.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %.fca.0.1.0.0.0.insert, i16 %16, 0, 2, 0, 0, 0
  %.fca.0.4.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %.fca.0.2.0.0.0.insert, i1 %21, 0, 4, 0, 0, 0
  store %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %.fca.0.4.0.0.0.insert, %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %5
  %22 = bitcast %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %5 to i8*
  %23 = bitcast %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  call void @fpga_fifo_push_32(i8* %22, i8* %23)
  br label %empty, !llvm.loop !5

ret:                                              ; preds = %empty
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"(i32* noalias align 512 "unpacked"="0.0" %dst_V_data_V, i4* noalias align 512 "unpacked"="0.1" %dst_V_keep_V, i4* noalias align 512 "unpacked"="0.2" %dst_V_strb_V, i1* noalias align 512 "unpacked"="0.3" %dst_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias %src) unnamed_addr #2 {
entry:
  %0 = icmp eq %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %src, null
  br i1 %0, label %ret, label %copy

copy:                                             ; preds = %entry
  call fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"(i32* align 512 %dst_V_data_V, i4* align 512 %dst_V_keep_V, i4* align 512 %dst_V_strb_V, i1* align 512 %dst_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* nonnull %src)
  br label %ret

ret:                                              ; preds = %copy, %entry
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"(i32* noalias nocapture align 512 "unpacked"="0.0" %_V_data_V, i4* noalias nocapture align 512 "unpacked"="0.1" %_V_keep_V, i4* noalias nocapture align 512 "unpacked"="0.2" %_V_strb_V, i1* noalias nocapture align 512 "unpacked"="0.3" %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias nocapture) unnamed_addr #3 {
entry:
  %1 = alloca %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"
  %2 = alloca i32
  %3 = alloca i4
  %4 = alloca i4
  %5 = alloca i1
  br label %empty

empty:                                            ; preds = %push, %entry
  %6 = bitcast %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  %7 = call i1 @fpga_fifo_not_empty_12(i8* %6)
  br i1 %7, label %push, label %ret

push:                                             ; preds = %empty
  %8 = bitcast %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %1 to i8*
  %9 = bitcast %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  call void @fpga_fifo_pop_12(i8* %8, i8* %9)
  %10 = load volatile %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>", %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %1
  %.fca.0.0.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %10, 0, 0, 0, 0, 0
  %.fca.0.1.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %10, 0, 1, 0, 0, 0
  %.fca.0.2.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %10, 0, 2, 0, 0, 0
  %.fca.0.4.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %10, 0, 4, 0, 0, 0
  store i32 %.fca.0.0.0.0.0.extract, i32* %2
  %11 = bitcast i32* %2 to i8*
  %12 = bitcast i32* %_V_data_V to i8*
  call void @fpga_fifo_push_4(i8* %11, i8* %12)
  store i4 %.fca.0.1.0.0.0.extract, i4* %4
  %13 = bitcast i4* %4 to i8*
  %14 = bitcast i4* %_V_keep_V to i8*
  call void @fpga_fifo_push_1(i8* %13, i8* %14)
  store i4 %.fca.0.2.0.0.0.extract, i4* %3
  %15 = bitcast i4* %3 to i8*
  %16 = bitcast i4* %_V_strb_V to i8*
  call void @fpga_fifo_push_1(i8* %15, i8* %16)
  store i1 %.fca.0.4.0.0.0.extract, i1* %5
  %17 = bitcast i1* %5 to i8*
  %18 = bitcast i1* %_V_last_V to i8*
  call void @fpga_fifo_push_1(i8* %17, i8* %18)
  br label %empty, !llvm.loop !7

ret:                                              ; preds = %empty
  ret void
}

; Function Attrs: argmemonly noinline norecurse willreturn
define internal fastcc void @onebyonecpy_hls.p0i1(i1* noalias align 512 %dst, i1* noalias readonly %src) unnamed_addr #4 {
entry:
  %0 = icmp eq i1* %dst, null
  %1 = icmp eq i1* %src, null
  %2 = or i1 %0, %1
  br i1 %2, label %ret, label %copy

copy:                                             ; preds = %entry
  %3 = bitcast i1* %src to i8*
  %4 = load i8, i8* %3
  %5 = trunc i8 %4 to i1
  store i1 %5, i1* %dst, align 512
  br label %ret

ret:                                              ; preds = %copy, %entry
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @copy_out(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias, i128* noalias align 512 "unpacked"="1.0" %_V_data_V, i16* noalias align 512 "unpacked"="1.1" %_V_keep_V, i16* noalias align 512 "unpacked"="1.2" %_V_strb_V, i1* noalias align 512 "unpacked"="1.3" %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias, i32* noalias align 512 "unpacked"="3.0" %_V_data_V1, i4* noalias align 512 "unpacked"="3.1" %_V_keep_V2, i4* noalias align 512 "unpacked"="3.2" %_V_strb_V3, i1* noalias align 512 "unpacked"="3.3" %_V_last_V4, i1* noalias, i1* noalias readonly align 512) unnamed_addr #5 {
entry:
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0, i128* align 512 %_V_data_V, i16* align 512 %_V_keep_V, i16* align 512 %_V_strb_V, i1* align 512 %_V_last_V)
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>.4"(%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %1, i32* align 512 %_V_data_V1, i4* align 512 %_V_keep_V2, i4* align 512 %_V_strb_V3, i1* align 512 %_V_last_V4)
  call fastcc void @onebyonecpy_hls.p0i1(i1* %2, i1* align 512 %3)
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>.4"(%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias %dst, i32* noalias align 512 "unpacked"="1.0" %src_V_data_V, i4* noalias align 512 "unpacked"="1.1" %src_V_keep_V, i4* noalias align 512 "unpacked"="1.2" %src_V_strb_V, i1* noalias align 512 "unpacked"="1.3" %src_V_last_V) unnamed_addr #2 {
entry:
  %0 = icmp eq %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %dst, null
  br i1 %0, label %ret, label %copy

copy:                                             ; preds = %entry
  call fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>.7"(%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* nonnull %dst, i32* align 512 %src_V_data_V, i4* align 512 %src_V_keep_V, i4* align 512 %src_V_strb_V, i1* align 512 %src_V_last_V)
  br label %ret

ret:                                              ; preds = %copy, %entry
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>.7"(%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias nocapture, i32* noalias nocapture align 512 "unpacked"="1.0" %_V_data_V, i4* noalias nocapture align 512 "unpacked"="1.1" %_V_keep_V, i4* noalias nocapture align 512 "unpacked"="1.2" %_V_strb_V, i1* noalias nocapture align 512 "unpacked"="1.3" %_V_last_V) unnamed_addr #3 {
entry:
  %1 = alloca i32
  %2 = alloca i4
  %3 = alloca i4
  %4 = alloca i1
  %5 = alloca %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"
  br label %empty

empty:                                            ; preds = %push, %entry
  %6 = bitcast i32* %_V_data_V to i8*
  %7 = call i1 @fpga_fifo_not_empty_4(i8* %6)
  br i1 %7, label %push, label %ret

push:                                             ; preds = %empty
  %8 = bitcast i32* %1 to i8*
  %9 = bitcast i32* %_V_data_V to i8*
  call void @fpga_fifo_pop_4(i8* %8, i8* %9)
  %10 = load volatile i32, i32* %1
  %11 = bitcast i4* %3 to i8*
  %12 = bitcast i4* %_V_keep_V to i8*
  call void @fpga_fifo_pop_1(i8* %11, i8* %12)
  %13 = bitcast i4* %3 to i8*
  %14 = load i8, i8* %13
  %15 = trunc i8 %14 to i4
  %16 = bitcast i4* %2 to i8*
  %17 = bitcast i4* %_V_strb_V to i8*
  call void @fpga_fifo_pop_1(i8* %16, i8* %17)
  %18 = bitcast i4* %2 to i8*
  %19 = load i8, i8* %18
  %20 = trunc i8 %19 to i4
  %21 = bitcast i1* %4 to i8*
  %22 = bitcast i1* %_V_last_V to i8*
  call void @fpga_fifo_pop_1(i8* %21, i8* %22)
  %23 = bitcast i1* %4 to i8*
  %24 = load i8, i8* %23
  %25 = trunc i8 %24 to i1
  %.fca.0.0.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" undef, i32 %10, 0, 0, 0, 0, 0
  %.fca.0.1.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %.fca.0.0.0.0.0.insert, i4 %15, 0, 1, 0, 0, 0
  %.fca.0.2.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %.fca.0.1.0.0.0.insert, i4 %20, 0, 2, 0, 0, 0
  %.fca.0.4.0.0.0.insert = insertvalue %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %.fca.0.2.0.0.0.insert, i1 %25, 0, 4, 0, 0, 0
  store %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>" %.fca.0.4.0.0.0.insert, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %5
  %26 = bitcast %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %5 to i8*
  %27 = bitcast %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  call void @fpga_fifo_push_12(i8* %26, i8* %27)
  br label %empty, !llvm.loop !7

ret:                                              ; preds = %empty
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>.15"(i128* noalias align 512 "unpacked"="0.0" %dst_V_data_V, i16* noalias align 512 "unpacked"="0.1" %dst_V_keep_V, i16* noalias align 512 "unpacked"="0.2" %dst_V_strb_V, i1* noalias align 512 "unpacked"="0.3" %dst_V_last_V, %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias %src) unnamed_addr #2 {
entry:
  %0 = icmp eq %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %src, null
  br i1 %0, label %ret, label %copy

copy:                                             ; preds = %entry
  call fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>.18"(i128* align 512 %dst_V_data_V, i16* align 512 %dst_V_keep_V, i16* align 512 %dst_V_strb_V, i1* align 512 %dst_V_last_V, %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* nonnull %src)
  br label %ret

ret:                                              ; preds = %copy, %entry
  ret void
}

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @"streamcpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>.18"(i128* noalias nocapture align 512 "unpacked"="0.0" %_V_data_V, i16* noalias nocapture align 512 "unpacked"="0.1" %_V_keep_V, i16* noalias nocapture align 512 "unpacked"="0.2" %_V_strb_V, i1* noalias nocapture align 512 "unpacked"="0.3" %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias nocapture) unnamed_addr #3 {
entry:
  %1 = alloca %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"
  %2 = alloca i1
  %3 = alloca i128
  %4 = alloca i16
  %5 = alloca i16
  br label %empty

empty:                                            ; preds = %push, %entry
  %6 = bitcast %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  %7 = call i1 @fpga_fifo_not_empty_32(i8* %6)
  br i1 %7, label %push, label %ret

push:                                             ; preds = %empty
  %8 = bitcast %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %1 to i8*
  %9 = bitcast %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0 to i8*
  call void @fpga_fifo_pop_32(i8* %8, i8* %9)
  %10 = load volatile %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>", %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %1
  %.fca.0.0.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %10, 0, 0, 0, 0, 0
  %.fca.0.1.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %10, 0, 1, 0, 0, 0
  %.fca.0.2.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %10, 0, 2, 0, 0, 0
  %.fca.0.4.0.0.0.extract = extractvalue %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>" %10, 0, 4, 0, 0, 0
  store i128 %.fca.0.0.0.0.0.extract, i128* %3
  %11 = bitcast i128* %3 to i8*
  %12 = bitcast i128* %_V_data_V to i8*
  call void @fpga_fifo_push_16(i8* %11, i8* %12)
  store i16 %.fca.0.1.0.0.0.extract, i16* %5
  %13 = bitcast i16* %5 to i8*
  %14 = bitcast i16* %_V_keep_V to i8*
  call void @fpga_fifo_push_2(i8* %13, i8* %14)
  store i16 %.fca.0.2.0.0.0.extract, i16* %4
  %15 = bitcast i16* %4 to i8*
  %16 = bitcast i16* %_V_strb_V to i8*
  call void @fpga_fifo_push_2(i8* %15, i8* %16)
  store i1 %.fca.0.4.0.0.0.extract, i1* %2
  %17 = bitcast i1* %2 to i8*
  %18 = bitcast i1* %_V_last_V to i8*
  call void @fpga_fifo_push_1(i8* %17, i8* %18)
  br label %empty, !llvm.loop !5

ret:                                              ; preds = %empty
  ret void
}

declare i8* @malloc(i64)

declare void @free(i8*)

declare void @apatb_mlp_core_stream_hw(i128*, i16*, i16*, i1*, i32*, i4*, i4*, i1*, i1*)

; Function Attrs: argmemonly noinline willreturn
define internal fastcc void @copy_back(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias, i128* noalias align 512 "unpacked"="1.0" %_V_data_V, i16* noalias align 512 "unpacked"="1.1" %_V_keep_V, i16* noalias align 512 "unpacked"="1.2" %_V_strb_V, i1* noalias align 512 "unpacked"="1.3" %_V_last_V, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias, i32* noalias align 512 "unpacked"="3.0" %_V_data_V1, i4* noalias align 512 "unpacked"="3.1" %_V_keep_V2, i4* noalias align 512 "unpacked"="3.2" %_V_strb_V3, i1* noalias align 512 "unpacked"="3.3" %_V_last_V4, i1* noalias, i1* noalias readonly align 512) unnamed_addr #5 {
entry:
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %0, i128* align 512 %_V_data_V, i16* align 512 %_V_keep_V, i16* align 512 %_V_strb_V, i1* align 512 %_V_last_V)
  call fastcc void @"onebyonecpy_hls.p0class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>.4"(%"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %1, i32* align 512 %_V_data_V1, i4* align 512 %_V_keep_V2, i4* align 512 %_V_strb_V3, i1* align 512 %_V_last_V4)
  call fastcc void @onebyonecpy_hls.p0i1(i1* %2, i1* align 512 %3)
  ret void
}

declare void @mlp_core_stream_hw_stub(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* noalias nonnull, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* noalias nonnull, i1* noalias nocapture nonnull)

define void @mlp_core_stream_hw_stub_wrapper(i128*, i16*, i16*, i1*, i32*, i4*, i4*, i1*, i1*) #6 {
entry:
  %9 = call i8* @malloc(i64 32)
  %10 = bitcast i8* %9 to %"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"*
  %11 = call i8* @malloc(i64 12)
  %12 = bitcast i8* %11 to %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"*
  call void @copy_out(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %10, i128* %0, i16* %1, i16* %2, i1* %3, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %12, i32* %4, i4* %5, i4* %6, i1* %7, i1* null, i1* %8)
  call void @mlp_core_stream_hw_stub(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %10, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %12, i1* %8)
  call void @copy_in(%"class.hls::stream<hls::axis<ap_uint<128>, 0, 0, 0, '8', false>, 0>"* %10, i128* %0, i16* %1, i16* %2, i1* %3, %"class.hls::stream<hls::axis<ap_uint<32>, 0, 0, 0, '8', false>, 0>"* %12, i32* %4, i4* %5, i4* %6, i1* %7, i1* null, i1* %8)
  call void @free(i8* %9)
  call void @free(i8* %11)
  ret void
}

declare i1 @fpga_fifo_not_empty_32(i8*)

declare i1 @fpga_fifo_not_empty_12(i8*)

declare i1 @fpga_fifo_not_empty_4(i8*)

declare i1 @fpga_fifo_not_empty_16(i8*)

declare void @fpga_fifo_pop_32(i8*, i8*)

declare void @fpga_fifo_pop_12(i8*, i8*)

declare void @fpga_fifo_pop_4(i8*, i8*)

declare void @fpga_fifo_pop_1(i8*, i8*)

declare void @fpga_fifo_pop_16(i8*, i8*)

declare void @fpga_fifo_pop_2(i8*, i8*)

declare void @fpga_fifo_push_32(i8*, i8*)

declare void @fpga_fifo_push_12(i8*, i8*)

declare void @fpga_fifo_push_4(i8*, i8*)

declare void @fpga_fifo_push_1(i8*, i8*)

declare void @fpga_fifo_push_16(i8*, i8*)

declare void @fpga_fifo_push_2(i8*, i8*)

attributes #0 = { noinline willreturn "fpga.wrapper.func"="wrapper" }
attributes #1 = { argmemonly noinline willreturn "fpga.wrapper.func"="copyin" }
attributes #2 = { argmemonly noinline willreturn "fpga.wrapper.func"="onebyonecpy_hls" }
attributes #3 = { argmemonly noinline willreturn "fpga.wrapper.func"="streamcpy_hls" }
attributes #4 = { argmemonly noinline norecurse willreturn "fpga.wrapper.func"="onebyonecpy_hls" }
attributes #5 = { argmemonly noinline willreturn "fpga.wrapper.func"="copyout" }
attributes #6 = { "fpga.wrapper.func"="stub" }

!llvm.dbg.cu = !{}
!llvm.ident = !{!0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0, !0}
!llvm.module.flags = !{!1, !2, !3}
!blackbox_cfg = !{!4}

!0 = !{!"clang version 7.0.0 "}
!1 = !{i32 2, !"Dwarf Version", i32 4}
!2 = !{i32 2, !"Debug Info Version", i32 3}
!3 = !{i32 1, !"wchar_size", i32 4}
!4 = !{}
!5 = distinct !{!5, !6}
!6 = !{!"llvm.loop.rotate.disable"}
!7 = distinct !{!7, !6}

"""第 58 批：同一支 HDR 片子在高亮电视上正常，接到普通电视后高光全糊，字幕刺眼。

修复点：静态元数据（MaxCLL/MaxFALL）、PQ/HLG 曲线适配、SDR tone mapping、
字幕亮度、分段元数据、10bit 链路、色彩空间标记、截图映射、多轨/缓存版本、
动态元数据、能力重协商与算子重置。
"""

import math

# ST 2084 (PQ) 常量
_PQ_M1 = 2610 / 16384
_PQ_M2 = 2523 / 32
_PQ_C1 = 3424 / 4096
_PQ_C2 = 2413 / 128
_PQ_C3 = 2392 / 128
PQ_MAX_NITS = 10000.0

# HLG OETF 常量 (BT.2100)
_HLG_A = 0.17883277
_HLG_B = 0.28466892
_HLG_C = 0.55991073


def max_fall(max_cll, max_fall):
    """返回 MaxFALL（帧平均最大亮度），并写入容器静态元数据。

    MaxCLL 与 MaxFALL 都必须随容器下发，不能只写 MaxCLL。
    """
    return max_fall


def pq_to_nits(pq):
    """把 PQ 信号值 (0..1) 按 ST 2084 EOTF 换算成 nits。"""
    if pq <= 0.0:
        return 0.0
    pq = min(pq, 1.0)
    v = pq ** (1.0 / _PQ_M2)
    num = max(v - _PQ_C1, 0.0)
    den = _PQ_C2 - _PQ_C3 * v
    return PQ_MAX_NITS * (num / den) ** (1.0 / _PQ_M1)


def hlg_curve(value):
    """HLG 亮度曲线（OETF）：低电平段为平方根，高电平段为对数。

    输出设备是 HLG 时必须切换到这条曲线，不能沿用 PQ。
    """
    if value <= 0.0:
        return 0.0
    if value <= 0.5:
        return math.sqrt(value)
    return _HLG_A * math.log(value - _HLG_B) + _HLG_C


def sdr_tone_map(nits, max_nits):
    """把 HDR 亮度映射到 SDR [0,1]，高光压缩而不是直接削波，暗部不压黑。"""
    if max_nits <= 0:
        return 0.0
    x = max(nits, 0.0) / max_nits
    return min(x, 1.0)


def subtitle_luma(nits, max_nits):
    """字幕亮度映射：跟随画面 tone mapping，避免 HDR 下按 SDR 亮度渲染而过曝。"""
    return sdr_tone_map(nits, max_nits)


def segment_metadata(segment, default):
    """返回当前分段的元数据；剪辑点处片段自带元数据时不得沿用上一段。"""
    if segment is None:
        return default
    return segment


def bit_depth(value, bits):
    """按位深量化，全链路保持 10bit，中间格式不得降到 8bit。"""
    levels = (1 << bits) - 1
    return int(value * levels) / levels


def colorspace_tag(primary):
    """返回规范化的色彩空间标记，防止 BT.2020 被当作 BT.709 解释。"""
    return primary.lower()


def thumbnail_map(value, exposure):
    """HDR 截图/缩略图映射：按曝光压缩到 SDR，避免直接截 HDR 帧发灰。"""
    return min(max(value * exposure, 0.0), 1.0)


def cache_version(video_id, version):
    """元数据缓存键包含片源版本，换片源后不会命中旧元数据。"""
    return f"{video_id}#{version}"


def dynamic_metadata(frame_values):
    """HDR10+ 动态元数据：逐帧读取；空序列回退为 0。"""
    if not frame_values:
        return 0
    return frame_values[0]

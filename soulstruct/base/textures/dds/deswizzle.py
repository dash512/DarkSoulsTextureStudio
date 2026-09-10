"""Console DDS deswizzle methods, adapted from `DrSwizzler` by Shadowth117.

See:
    https://github.com/Shadowth117/DrSwizzler
"""
from __future__ import annotations

__all__ = [
    "DDSDeswizzleError",
    "deswizzle_dds_bytes_ps3",
    "deswizzle_dds_bytes_ps4",
]

from math import ceil
from soulstruct.exceptions import SoulstructError
from .enums import *
from .utilities import *
from DSTS.Utilities import morton8 # Added in DSTS (duh)


class DDSDeswizzleError(SoulstructError):
    """Base DDS deswizzler error."""


def deswizzle_dds_bytes_ps3(swizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int) -> bytes:
    bits_per_pixel, pixel_block_size, dds_bytes_per_pixel_set = dxgi_format.get_format_info()

    if dds_bytes_per_pixel_set >= len(swizzled):
        raise DDSDeswizzleError(
            f"DDS texture is too small to contain a single pixel set (expected {dds_bytes_per_pixel_set} bytes)."
        )
    deswizzled_size = max((width * height * bits_per_pixel) // 8, dds_bytes_per_pixel_set)
    deswizzled = bytearray(b"\0" * deswizzled_size)
    sy = height // pixel_block_size
    sx = width // pixel_block_size
    for src_tile_i in range(sx * sy):
        dest_tile_i = morton(src_tile_i, sx, sy)
        swizzled_start = src_tile_i * dds_bytes_per_pixel_set
        swizzled_tile = swizzled[swizzled_start:swizzled_start + dds_bytes_per_pixel_set]
        deswizzled_start = dest_tile_i * dds_bytes_per_pixel_set
        deswizzled[deswizzled_start:deswizzled_start + dds_bytes_per_pixel_set] = swizzled_tile

    return bytes(deswizzled)


"""Rewritten in DSTS, not original to Soulstruct."""
def deswizzle_dds_bytes_ps4(swizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int ) -> bytes:
    _, pixel_block_size, block_bytes = dxgi_format.get_format_info()

    sx = max(1, ceil(width / pixel_block_size))
    sy = max(1, ceil(height / pixel_block_size))

    linear_size = sx * sy * block_bytes
    out = bytearray(linear_size)

    stream_pos = 0

    for macro_y in range((sy + 7) // 8):
        for macro_x in range((sx + 7) // 8):
            for t in range(64):
                tile_x, tile_y = morton8(t)

                if stream_pos + block_bytes > len(swizzled):
                    return bytes(out)
                
                if (macro_x * 8 + tile_x < sx) and (macro_y * 8 + tile_y < sy):
                    dst = (((macro_y * 8 + tile_y) * sx) + (macro_x * 8 + tile_x)) * block_bytes

                    out[dst:dst + block_bytes] = swizzled[stream_pos:stream_pos + block_bytes]

                stream_pos += block_bytes

    return bytes(out)
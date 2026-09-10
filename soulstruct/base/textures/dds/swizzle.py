"""Console DDS swizzle methods, adapted from `DrSwizzler` by Shadowth117.

The swizzle/deswizzle algorithms (for all consoles supported thus far) are identical, i.e. self-inverse.

See:
    https://github.com/Shadowth117/DrSwizzler
"""
from __future__ import annotations

__all__ = [
    "DDSSwizzleError",
    "swizzle_dds_bytes_ps3",
    "swizzle_dds_bytes_ps4",
]

from math import ceil
from soulstruct.exceptions import SoulstructError
from .enums import *
from .utilities import *
from DSTS.Utilities import morton8 # Added in DSTS (duh)


class DDSSwizzleError(SoulstructError):
    """Base DDS swizzler error."""


def swizzle_dds_bytes_ps3(deswizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int, min_data_size: int = 0) -> bytes:
    bits_per_pixel, pixel_block_size, dds_bytes_per_pixel_set = dxgi_format.get_format_info()
    if dds_bytes_per_pixel_set >= len(deswizzled):
        raise DDSSwizzleError(
            f"DDS texture is too small to contain a single pixel set (expected {dds_bytes_per_pixel_set} bytes)."
        )
    # Pad deswizzled data to minimum size if necessary.
    deswizzled += b"\0" * (min_data_size - len(deswizzled))
    swizzled_size = max((width * height * bits_per_pixel) // 8, min_data_size)
    swizzled = bytearray(b"\0" * swizzled_size)
    sy = height // pixel_block_size
    sx = width // pixel_block_size
    for src_tile_i in range(sx * sy):
        # Identical to PS3 deswizzling.
        dest_tile_i = morton(src_tile_i, sx, sy)
        deswizzled_start = src_tile_i * dds_bytes_per_pixel_set
        deswizzled_tile = deswizzled[deswizzled_start:deswizzled_start + dds_bytes_per_pixel_set]
        swizzled_start = dest_tile_i * dds_bytes_per_pixel_set
        swizzled[swizzled_start:swizzled_start + dds_bytes_per_pixel_set] = deswizzled_tile
    return bytes(swizzled)


"""Rewritten in DSTS, not original to Soulstruct."""
def swizzle_dds_bytes_ps4(deswizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int, min_data_size: int = 0x200) -> bytes:
    _, pixel_block_size, block_bytes = dxgi_format.get_format_info()

    sx = max(1, ceil(width / pixel_block_size))
    sy = max(1, ceil(height / pixel_block_size))

    linear_size = sx * sy * block_bytes
    deswizzled = deswizzled[:linear_size]

    out_size = max(((sx + 7) // 8) * ((sy + 7) // 8) * 64 * block_bytes, min_data_size)
    out = bytearray(out_size)

    stream_pos = 0

    for macro_y in range((sy + 7) // 8):
        for macro_x in range((sx + 7) // 8):
            for t in range(64):
                tile_x, tile_y = morton8(t)

                if (macro_x * 8 + tile_x < sx) and (macro_y * 8 + tile_y < sy):
                    src = (((macro_y * 8 + tile_y) * sx) + (macro_x * 8 + tile_x)) * block_bytes

                    if src <= len(deswizzled) - block_bytes:
                        out[stream_pos:stream_pos + block_bytes] = deswizzled[src:src + block_bytes]

                stream_pos += block_bytes

    return bytes(out)
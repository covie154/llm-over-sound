"""
LZNT1 compression and decompression — compatible with Windows RtlCompressBuffer / RtlDecompressBuffer.
"""


def lznt1_decompress(compressed: bytes, max_output_size: int = 262144) -> bytes:
    """Decompress LZNT1 compressed data."""
    output = bytearray()
    i = 0

    while i < len(compressed) - 1:
        # Read chunk header (2 bytes, little-endian)
        header = compressed[i] | (compressed[i + 1] << 8)
        i += 2

        if header == 0:
            break

        chunk_size = (header & 0xFFF) + 1
        is_compressed = bool(header & 0x8000)
        chunk_end = min(i + chunk_size, len(compressed))

        if not is_compressed:
            output.extend(compressed[i:chunk_end])
            i = chunk_end
            continue

        # Compressed chunk
        chunk_output_start = len(output)

        while i < chunk_end:
            if i >= len(compressed):
                break

            flags = compressed[i]
            i += 1

            for bit_idx in range(8):
                if i >= chunk_end:
                    break

                if len(output) >= max_output_size:
                    return bytes(output)

                if not (flags & (1 << bit_idx)):
                    # Literal byte
                    output.append(compressed[i])
                    i += 1
                else:
                    # Back-reference
                    if i + 1 >= len(compressed):
                        break

                    ref = compressed[i] | (compressed[i + 1] << 8)
                    i += 2

                    pos_in_chunk = len(output) - chunk_output_start
                    displacement_bits = max(4, pos_in_chunk.bit_length()) if pos_in_chunk > 0 else 4
                    length_bits = 16 - displacement_bits

                    length = (ref & ((1 << length_bits) - 1)) + 3
                    displacement = (ref >> length_bits) + 1

                    start = len(output) - displacement
                    if start < 0:
                        break

                    for j in range(length):
                        output.append(output[start + j])

    return bytes(output)


def lznt1_compress(data: bytes) -> bytes:
    """Compress data using LZNT1 algorithm."""
    result = bytearray()
    data_len = len(data)
    chunk_offset = 0

    while chunk_offset < data_len:
        chunk_end = min(chunk_offset + 4096, data_len)
        chunk_data = data[chunk_offset:chunk_end]

        compressed_chunk = _lznt1_compress_chunk(chunk_data)

        if compressed_chunk is not None and len(compressed_chunk) < len(chunk_data):
            # Bit 15 = 1 (compressed), bits 14-12 = 011 (signature = 3)
            header = 0xB000 | (len(compressed_chunk) - 1)
            result.append(header & 0xFF)
            result.append((header >> 8) & 0xFF)
            result.extend(compressed_chunk)
        else:
            # Bit 15 = 0 (uncompressed), bits 14-12 = 011 (signature = 3)
            header = 0x3000 | (len(chunk_data) - 1)
            result.append(header & 0xFF)
            result.append((header >> 8) & 0xFF)
            result.extend(chunk_data)

        chunk_offset = chunk_end

    return bytes(result)


def _lznt1_compress_chunk(data: bytes) -> bytearray:
    """Compress a single chunk of up to 4096 bytes using LZNT1."""
    result = bytearray()
    pos = 0
    data_len = len(data)

    while pos < data_len:
        flags_offset = len(result)
        result.append(0)  # Placeholder for flags byte
        flags = 0

        for bit_idx in range(8):
            if pos >= data_len:
                break

            best_len = 0
            best_disp = 0

            if pos > 0:
                displacement_bits = max(4, pos.bit_length())
                length_bits = 16 - displacement_bits
                max_match_len = min((1 << length_bits) + 2, data_len - pos)
                max_disp = min(1 << displacement_bits, pos)

                search_start = pos - max_disp
                for s in range(pos - 1, search_start - 1, -1):
                    match_len = 0
                    while (match_len < max_match_len and
                           pos + match_len < data_len and
                           data[s + match_len] == data[pos + match_len]):
                        match_len += 1

                    if match_len >= 3 and match_len > best_len:
                        best_len = match_len
                        best_disp = pos - s
                        if match_len >= max_match_len:
                            break

            if best_len >= 3:
                flags |= (1 << bit_idx)
                displacement_bits = max(4, pos.bit_length())
                length_bits = 16 - displacement_bits
                ref = ((best_disp - 1) << length_bits) | (best_len - 3)
                result.append(ref & 0xFF)
                result.append((ref >> 8) & 0xFF)
                pos += best_len
            else:
                result.append(data[pos])
                pos += 1

        result[flags_offset] = flags

    return result

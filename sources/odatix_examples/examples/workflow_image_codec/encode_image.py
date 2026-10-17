"""
A small block-transform image codec, encoded and measured for one setting of
its knobs.

Nothing here is specific to Odatix: it is an ordinary script, run once per
design, that writes what it measured to a json file. What makes it worth
exploring rather than sweeping is that its knobs pull against each other --
every one of them buys quality with bitrate, or bitrate with quality, and none
of them says which trade-off is the good one.

Written with the standard library only, and fast enough that a whole
exploration runs on a laptop in a couple of minutes.
"""

import argparse
import json
import math
import time

#: The image is the same for every design: two encoders are compared on one
#: picture, or they are not compared at all.
WIDTH = 96
HEIGHT = 96


def make_image():
    """
    A deterministic test image: a smooth gradient, a sharp edge, a textured
    corner and a little noise -- enough that a codec has both easy and hard
    parts to spend its bits on.
    """
    pixels = []
    seed = 12345
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            # A pseudo-random value, drawn the same way on every machine.
            seed = (1103515245 * seed + 12345) % 2147483648
            noise = (seed % 17) - 8

            value = 40.0 + 120.0 * (x + y) / float(WIDTH + HEIGHT)
            if x > 2 * WIDTH // 3:
                value += 60.0  # a sharp edge, which is what ringing shows up on
            if y > HEIGHT // 2:
                value += 40.0 * math.sin(x / 4.0) * math.cos(y / 6.0)  # texture
            row.append(max(0.0, min(255.0, value + noise)))
        pixels.append(row)
    return pixels


######################################
# The transform
######################################

def dct_matrix(n):
    """The DCT-II basis of size n, built once and reused by every block."""
    basis = []
    for k in range(n):
        scale = math.sqrt(1.0 / n) if k == 0 else math.sqrt(2.0 / n)
        basis.append([scale * math.cos(math.pi * (2 * i + 1) * k / (2.0 * n)) for i in range(n)])
    return basis


def transform(block, basis):
    """The 2D DCT of one block: the basis applied to its rows, then its columns."""
    n = len(block)
    rows = [[sum(basis[k][i] * block[j][i] for i in range(n)) for k in range(n)] for j in range(n)]
    return [[sum(basis[k][j] * rows[j][i] for j in range(n)) for i in range(n)] for k in range(n)]


def inverse(coefficients, basis):
    """The 2D inverse DCT, the same thing read the other way round."""
    n = len(coefficients)
    rows = [[sum(basis[k][j] * coefficients[k][i] for k in range(n)) for i in range(n)] for j in range(n)]
    return [[sum(basis[k][i] * rows[j][k] for k in range(n)) for i in range(n)] for j in range(n)]


######################################
# The entropy coder
######################################

#: The symbol that ends a block: everything left in it is zero.
END_OF_BLOCK = (0, 0)

#: The symbol that stands for sixteen zeros, when a run is longer than a single
#: symbol can name.
ZERO_RUN = (15, 0)


def zigzag_order(n):
    """
    The order the coefficients of a block are read in.

    Lowest frequencies first, walking the diagonals in alternating directions,
    so that the zeros the quantizer produces end up gathered at the tail of the
    block where one symbol can dismiss them all.
    """
    indices = [(u, v) for u in range(n) for v in range(n)]
    indices.sort(key=lambda uv: (uv[0] + uv[1], uv[0] if (uv[0] + uv[1]) % 2 else uv[1]))
    return indices


def magnitude_bits(level):
    """
    How many bits a non-zero level costs on top of its symbol: its magnitude
    and its sign, which is the "category" a JPEG-style coder sends verbatim.
    """
    return abs(level).bit_length()


def run_length_symbols(levels, order):
    """
    Turn one quantized block into the symbols a real coder would have to write.

    One (run of zeros, magnitude size) pair per non-zero coefficient, and one
    end-of-block symbol as soon as the rest of the block is zero -- which is
    what makes a long tail of zeros nearly free, however large the block is.

    Returns:
        tuple: the symbols of the block, and the raw bits their magnitudes and
        signs cost.
    """
    flat = [levels[u][v] for u, v in order]

    last = -1
    for index, level in enumerate(flat):
        if level != 0:
            last = index

    symbols = []
    raw_bits = 0.0
    run = 0
    for level in flat[:last + 1]:
        if level == 0:
            run += 1
            if run == 16:
                symbols.append(ZERO_RUN)
                run = 0
            continue
        size = magnitude_bits(level)
        symbols.append((run, size))
        raw_bits += size
        run = 0

    if last < len(flat) - 1:
        symbols.append(END_OF_BLOCK)
    return symbols, raw_bits


def entropy_bits(symbols):
    """
    What a symbol stream costs, at the order-0 entropy of its own distribution.

    This is the bound a Huffman or arithmetic coder comes within a few percent
    of, so it stands in for one here rather than tables being built and walked.
    It assumes one table shared by the whole image, and does not count the cost
    of sending that table.
    """
    total = sum(symbols.values())
    if total == 0:
        return 0.0
    bits = 0.0
    for count in symbols.values():
        bits += -count * math.log(count / float(total), 2)
    return bits


######################################
# The codec
######################################

def downsample(pixels, factor):
    """Average each factor x factor square into one pixel."""
    if factor <= 1:
        return pixels
    height = len(pixels) // factor
    width = len(pixels[0]) // factor
    small = []
    for y in range(height):
        row = []
        for x in range(width):
            total = 0.0
            for dy in range(factor):
                for dx in range(factor):
                    total += pixels[y * factor + dy][x * factor + dx]
            row.append(total / (factor * factor))
        small.append(row)
    return small


def upsample(pixels, factor, height, width):
    """Put a downsampled image back to size, one pixel repeated per square."""
    if factor <= 1:
        return pixels
    return [[pixels[min(y // factor, len(pixels) - 1)][min(x // factor, len(pixels[0]) - 1)]
             for x in range(width)] for y in range(height)]


def quantization_step(quality, u, v, block_size):
    """
    How coarsely one coefficient is quantized.

    Coarser as the quality drops, and coarser for the high frequencies than for
    the low ones -- the same idea every transform codec is built on, which is
    what makes "quality" trade bitrate against distortion rather than just
    scale everything.
    """
    quality = max(1.0, min(99.0, float(quality)))
    strength = (100.0 - quality) / 10.0
    frequency = 1.0 + 2.0 * (u + v) / float(2 * block_size)
    return max(1.0, strength * frequency)


def encode(pixels, block_size, quality, dead_zone):
    """
    Encode the image and decode it back.

    Returns:
        tuple: how many bits it took, and the image that comes back out.
    """
    basis = dct_matrix(block_size)
    order = zigzag_order(block_size)
    height = len(pixels)
    width = len(pixels[0])
    decoded = [[0.0] * width for _ in range(height)]
    # How many times each symbol was written, which is all the entropy coder
    # needs to know to price the whole image at the end.
    counts = {}
    raw_bits = 0.0

    for by in range(0, height - block_size + 1, block_size):
        for bx in range(0, width - block_size + 1, block_size):
            block = [[pixels[by + y][bx + x] - 128.0 for x in range(block_size)] for y in range(block_size)]
            coefficients = transform(block, basis)

            levels = []
            for u in range(block_size):
                row = []
                for v in range(block_size):
                    step = quantization_step(quality, u, v, block_size)
                    value = coefficients[u][v]
                    # The dead zone widens the interval that quantizes to zero:
                    # cheaper, and blurrier.
                    if abs(value) < step * (0.5 + dead_zone / 100.0):
                        level = 0
                    else:
                        level = int(round(value / step))
                    row.append(level)
                levels.append(row)

            symbols, block_bits = run_length_symbols(levels, order)
            for symbol in symbols:
                counts[symbol] = counts.get(symbol, 0) + 1
            raw_bits += block_bits

            dequantized = [
                [levels[u][v] * quantization_step(quality, u, v, block_size) for v in range(block_size)]
                for u in range(block_size)
            ]
            reconstructed = inverse(dequantized, basis)
            for y in range(block_size):
                for x in range(block_size):
                    decoded[by + y][bx + x] = reconstructed[y][x] + 128.0

    return raw_bits + entropy_bits(counts), decoded


def psnr(original, decoded):
    """How close what comes out is to what went in, in dB."""
    total = 0.0
    count = 0
    for y in range(len(original)):
        for x in range(len(original[0])):
            error = original[y][x] - decoded[y][x]
            total += error * error
            count += 1
    mse = total / max(count, 1)
    if mse <= 1e-9:
        return 99.0
    return 10.0 * math.log(255.0 * 255.0 / mse, 10)


def main():
    parser = argparse.ArgumentParser(description="Encode a test image with one setting of the codec")
    parser.add_argument("--block_size", type=int, required=True, help="transform block size, in pixels")
    parser.add_argument("--quality", type=int, required=True, help="quantization quality, 1 (coarse) to 99 (fine)")
    parser.add_argument("--downsample", type=int, required=True, help="1: full resolution, 2: half, 4: quarter")
    parser.add_argument("--dead_zone", type=int, required=True, help="how much wider the zero interval is, in %%")
    arguments = parser.parse_args()

    original = make_image()

    with open("progress.txt", "w") as progress:
        progress.write("Progress: 10")

    started = time.time()
    small = downsample(original, arguments.downsample)
    bits, decoded_small = encode(small, arguments.block_size, arguments.quality, arguments.dead_zone)
    encode_time_ms = (time.time() - started) * 1000.0

    decoded = upsample(decoded_small, arguments.downsample, HEIGHT, WIDTH)

    results = {
        "bitrate_bpp": round(bits / float(WIDTH * HEIGHT), 6),
        "psnr_db": round(psnr(original, decoded), 4),
        "encode_time_ms": round(encode_time_ms, 3),
        "compressed_bytes": int(bits / 8.0),
    }

    with open("workflow_results.json", "w") as results_file:
        json.dump(results, results_file, indent=2)

    with open("progress.txt", "w") as progress:
        progress.write("Progress: 100")

    print("bitrate: {0} bpp, psnr: {1} dB, {2} ms".format(
        results["bitrate_bpp"], results["psnr_db"], results["encode_time_ms"]
    ))


if __name__ == "__main__":
    main()

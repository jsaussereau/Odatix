# **********************************************************************
#                                Odatix
# **********************************************************************
#
# Bit-accurate model of the pipelined CORDIC rotation core
# (examples/cordic_sv/cordic.sv), measured the way its testbench measures it
# (examples/cordic_tb/tb_cordic.sv): same 512 vectors over a full turn, same
# floating-point reference, same error figures.
#
# It runs in a fraction of a second and needs nothing but Python, which makes
# it the place to explore the width and the number of stages before writing
# or simulating any RTL. On a configuration the RTL also has, it gives the
# same numbers as the simulation, to the last digit. It also estimates what
# the core costs (adder_bits), which is what an exploration of the model
# trades the accuracy against.

import argparse
import math

NB_VECTORS = 512
ANGLE_STEP = 2**32 // NB_VECTORS


def wrap(value, bits):
    """Two's complement wrap-around of a signed value on a number of bits."""
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def atan_lut(i):
    """atan(2^-i), with a full turn mapped to 2^32, as the RTL tabulates it."""
    # The RTL stops its table at 23, and rotates by 0 beyond
    if i > 23:
        return 0
    return int(round(math.atan(2.0 ** -i) * 2**32 / (2 * math.pi)))


def cordic(x, y, angle, width, iterations):
    """One rotation, bit for bit what the RTL computes."""
    iw = width + 2
    quadrant = (angle >> 30) & 3
    # Argument reduction: bring the angle back into [-90 deg, +90 deg]
    if quadrant == 1:
        x, y, z = -y, x, angle - 0x40000000
    elif quadrant == 2:
        x, y, z = y, -x, angle + 0x40000000
    else:
        z = angle
    x, y, z = wrap(x, iw), wrap(y, iw), wrap(z, 32)
    # Rotation stages: the arithmetic shift truncates, as >>> does
    for i in range(iterations):
        dx, dy = y >> i, x >> i
        if z < 0:
            x, y, z = x + dx, y - dy, z + atan_lut(i)
        else:
            x, y, z = x - dx, y + dy, z - atan_lut(i)
        x, y, z = wrap(x, iw), wrap(y, iw), wrap(z, 32)
    # Saturating output register
    top = (1 << (width - 1)) - 1
    return max(-top - 1, min(top, x)), max(-top - 1, min(top, y))


def measure(width, iterations):
    gain = 1.0
    for i in range(iterations):
        gain *= math.sqrt(1.0 + 2.0 ** (-2 * i))
    full_scale = 2.0 ** (width - 1) - 1.0
    magnitude = math.floor(0.55 * full_scale / gain)

    sum_sq_error = sum_sq_signal = sum_error = max_error = 0.0
    for n in range(NB_VECTORS):
        angle_fixed = (n - NB_VECTORS // 2) * ANGLE_STEP
        angle = angle_fixed * 2.0 * math.pi / 2**32
        ref_x = gain * magnitude * math.cos(angle)
        ref_y = gain * magnitude * math.sin(angle)
        out_x, out_y = cordic(int(magnitude), 0, angle_fixed, width, iterations)
        err = math.hypot(out_x - ref_x, out_y - ref_y)
        sum_error += err
        sum_sq_error += err * err
        sum_sq_signal += ref_x * ref_x + ref_y * ref_y
        max_error = max(max_error, err)

    rms_error = math.sqrt(sum_sq_error / NB_VECTORS)
    rms_signal = math.sqrt(sum_sq_signal / NB_VECTORS)
    return {
        "max_error_lsb": max_error,
        "rms_error_lsb": rms_error,
        "mean_error_lsb": sum_error / NB_VECTORS,
        "snr_db": 20.0 * math.log10(rms_signal / rms_error) if rms_error > 0 else 0.0,
        "enob": width - math.log2(rms_error * math.sqrt(12.0)) if rms_error > 0 else float(width),
        "latency_cycles": iterations + 1,
        "adder_bits": adder_bits(width, iterations),
    }


def adder_bits(width, iterations):
    """
    What the core costs, before any synthesis: the bits of its adders. Each
    stage adds on x and y (width + 2 bits each) and on the angle (32 bits).
    On an FPGA, one adder bit is about one LUT: this tracks the LUT count of
    Vivado on Artix-7 within a few percent.
    """
    return iterations * (2 * (width + 2) + 32)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bit-accurate model of the CORDIC core")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    args = parser.parse_args()

    results = measure(args.width, args.iterations)
    with open("results.yml", "w") as f:
        for key, value in results.items():
            f.write("%s: %s\n" % (key, round(value, 6)))
    for key, value in results.items():
        print("%-15s: %s" % (key, round(value, 6)))

    with open("progress.txt", "w") as f:
        f.write("Progress: 100\n")

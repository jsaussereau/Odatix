import argparse
import csv
import math

# Simulate a BER/FER sweep over a range of EBNO (Eb/N0) values.
# This mimics a typical communication-system simulation that reports
# several metric values (one per EBNO point) instead of a single result.


def simulate_point(ebno_db, channel_gain):
    # Rough Q-function approximation of a BER curve, just for demo purposes.
    snr = channel_gain * (10 ** (ebno_db / 5.0))
    ber = 0.5 * math.erfc(math.sqrt(snr))
    ber = max(ber, 1e-6)
    fer = min(1.0, ber * 3)
    n_frames = int(1000 / max(fer, 1e-3))
    n_frames = min(n_frames, 200000)
    n_fe = max(1, int(n_frames * fer))
    return ber, fer, n_frames, n_fe


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo workflow: BER/FER sweep exported as a multi-row CSV")
    parser.add_argument("--channel_gain", type=float, required=True)
    parser.add_argument("--ebno_from", type=float, default=1.0)
    parser.add_argument("--ebno_to", type=float, default=3.0)
    parser.add_argument("--ebno_step", type=float, default=0.5)
    args = parser.parse_args()

    rows = []
    ebno = args.ebno_from
    while ebno <= args.ebno_to + 1e-9:
        ber, fer, n_frames, n_fe = simulate_point(ebno, args.channel_gain)
        rows.append([round(ebno, 4), fer, ber, n_frames, n_fe])
        ebno += args.ebno_step

    with open("results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["EBNO", "FER", "BER", "N_FRA", "N_FE"])
        writer.writerows(rows)

    print("BER/FER sweep completed. Results saved to results.csv.")

    with open("progress.txt", "w") as f:
        f.write("Progress: 100%")

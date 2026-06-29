import argparse


def ascii_sum(text):
    return sum(ord(c) for c in text)


def compute_complexity(profile_name):
    score = (len(profile_name) * 1.75) + ((ascii_sum(profile_name) % 37) / 10.0)
    return round(score, 3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo workflow that consumes a profile from workflow config")
    parser.add_argument("--profile", required=True, help="Profile string injected from workflow config")
    parser.add_argument("--tag", default="demo", help="Static execution tag")
    args = parser.parse_args()

    profile = str(args.profile).strip()
    score = compute_complexity(profile)
    profile_ascii_sum = ascii_sum(profile)

    with open("output.txt", "w") as f:
        f.write("profile: " + profile + "\n")
        f.write("tag: " + str(args.tag) + "\n")
        f.write("ascii_sum: " + str(profile_ascii_sum) + "\n")
        f.write("complexity_score: " + str(score) + "\n")

    with open("progress.txt", "w") as f:
        f.write("Progress: 100%")

    print("Profile workflow finished for:", profile)

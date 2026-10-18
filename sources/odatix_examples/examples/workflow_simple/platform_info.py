import sys

# what the "platform" metric of the "crossplatform" workflow reads
with open("platform_info.txt", "w") as f:
    f.write("platform: " + sys.platform + "\n")

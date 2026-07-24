AWESOME_STRING = "default string"

# print in the terminal
print(AWESOME_STRING)

# print in a text file 
with open("output.txt", "w") as f:
    f.write("text: " + AWESOME_STRING + "\n")
    f.write("letters: " + str(len(AWESOME_STRING)) + "\n")

with open("progress.txt", "w") as f:
    f.write("Progress: 100%")

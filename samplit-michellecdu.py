import sys
import random

filename = sys.argv[1]
output = []

this_class = "data136"
scores = [100, 78, 80, 94]

with open(filename, "r") as f:
	for line in f:
		if random.random() < 0.01:
			 output.append(line)

print("".join(output))

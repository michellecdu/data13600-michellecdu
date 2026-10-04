import sys
import random

filename = sys.argv[1]
output = []

my_name = "Michelle Du"

with open(filename, "r") as f:
	for line in f:
		if random.random() < 0.01:
			 output.append(line)

print("".join(output))

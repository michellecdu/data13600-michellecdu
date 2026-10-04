import sys
import random

filename = sys.argv[1]
output = []

my_name = "Michelle Du"

ten = 2 + 8

with open(filename, "r") as f:
	for line in f:
		if random.random() < 0.01:
			 output.append(line)

print("".join(output))

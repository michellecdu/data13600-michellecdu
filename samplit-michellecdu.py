import sys
import random

filename = sys.argv[1]
output = []

my_name = "michelle"

ten = 6 + 4

with open(filename, "r") as f:
	for line in f:
		if random.random() < 0.01:
			 output.append(line)

print("".join(output))

"""
**************************************

Created in 12.09.2025
by Aiyyskhan Alekseev

**************************************
"""

import numpy as np

class NNet:
	def __init__(self):
		self.relu = lambda x: (np.absolute(x) + x) / 2
		self.weight_list = []

	def __call__(self, input_data):
		input_data = np.array(input_data)
		
		potentials = self.relu(np.tanh(np.matmul(input_data, self.weight_list[0])))

		potentials = self.relu(np.tanh(np.matmul(potentials, self.weight_list[1])))
		
		output = self.relu(np.tanh(np.matmul(potentials, self.weight_list[2])))

		return output

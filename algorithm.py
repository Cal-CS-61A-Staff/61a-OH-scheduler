from cvxpy import *
import numpy as np
import cvxpy as cp

def run_algorithm(inputs):
    input_demand = inputs[0]                # (# of future weeks, 5, 12)
    input_prev_assignments = inputs[1]      # (# of past weeks, # of day one staff, 5, 12)
    input_availabilities = inputs[2]        # (# of all staff, 5, 12)
    input_max_weekly_hours = inputs[3]      # (# of all staff, )
    #input_target_total_c
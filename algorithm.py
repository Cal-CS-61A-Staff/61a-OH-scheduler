from cvxpy import *
import numpy as np
import cvxpy as cp
from time import perf_counter

# Defining weights
U_3_1 = 400
U_3_2 = 50
U_3_3 = 700
U_3_4 = 50
U_3_5 = 100

# Weight fxn used in term 3.5 (consistent weekly hours)
lambda_func = lambda x: np.exp(-0.2 * x)

# Mapping between rating and displeasure used in term 3.4 (minimize displeasure)
RATE_TO_DISPLEASURE_MAPPING = {1: 0, 2: 2, 3: 8, 4: 16, 5: 1e8}



def var_to_np(decision_var):
    """Converts decision variable (np array of cp.Variable objects) into np array of integers

    Args:
        decision_var (np.ndarray): np array of cp.Variable objects

    Returns:
        np.ndarray of decision variable results
    """
    get_value = lambda var: var.value
    vfunc = np.vectorize(get_value)
    return vfunc(decision_var)

def run_algorithm(inputs):
    input_oh_demand = inputs[0]                         # (# of future weeks, 5, 12)
    input_previous_weeks_assignments = inputs[1]        # (# of day one staff, # of past weeks, 5, 12)
    input_staff_availabilities = inputs[2]              # (# of all staff, 5, 12)
    input_max_contig = inputs[3]                        # (# of all staff, )
    input_target_total_future_hours = inputs[4]         # (# of all staff, )
    input_target_weekly_hours = inputs[5]               # (# of all staff, )
    input_preferred_contiguous_hours = inputs[6]        # (# of all staff, )
    input_changed_hours_weightings = inputs[7]          # (# of day one staff, )
    input_non_day_one_indices = inputs[8]               # (# of non day one staff, )

    print(input_previous_weeks_assignments.shape)
    m = input_max_contig.shape[0]
    m_non_day_ones = input_non_day_one_indices.shape[0] # WARNING: assumes non-day one staff are 
                                                        # added to the end of each prev_assignments array
    m_day_ones = m - m_non_day_ones

    n = input_oh_demand.shape[0]
    n = 6 # TODO: change later

    try:
        p = input_previous_weeks_assignments.shape[1]
    except IndexError as e:
        p = None
        print("No previous weeks. Removing past consistency constraint.")

    print("Setting up algorithm...")
    # Define the decision variable
    A = np.empty(shape = (m, n, 5, 12), dtype = object)
    for i in range(m):
        for j in range(n):
            for k in range(5):
                for l in range(12):
                    A[i, j, k, l] = cp.Variable(boolean=True)
                    
    # ---------------- Hard Constraints (CP constraints) ----------------
    constraints = []

    # 2.1: Staff time slot existence (At least 1 staff member per NONZERO time slot)
    X_2_1 = np.sum(A, axis = 0)

    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                if input_oh_demand[week_i, day_i, hour_i] != 0:
                    constraints.append(X_2_1[week_i, day_i, hour_i] >= 1)

    # 2.2: Maximum Contiguous Hours (TODO: OFF FOR NOW)
    # for staff_i in range(m):
    #     for week_i in range(n):
    #         for day_i in range(5):
    #             window_size = (input_max_contig[staff_i] + 1)
    #             for start in range(12 - window_size + 1):
    #                 total = 0
    #                 for i in range(window_size):
    #                     total += A[staff_i, week_i, day_i, start + i]
    #                 constraints.append(total <= input_max_contig[staff_i])

    # 2.3 (TESTING) no timeslot should have > 2 number of absences
    X_2_3 = np.sum(A, axis=0)

    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                constraints.append(input_oh_demand[week_i, day_i, hour_i] - X_2_3[week_i, day_i, hour_i] <= 2)

    # 2.4 (TEMP/TESTING) no one should be doing >2+ their target weekly hours
    X_2_4 = A.sum((2, 3))
    T = input_target_weekly_hours[:, None].repeat(n, axis=1)
    for staff_i in range(m):
        for week_i in range(n):
            constraints.append(X_2_4[staff_i, week_i] - T[staff_i, week_i] <= 1)

    # 2.5 (TEMP/TESTING) no assignments during times of 0 demand
    X_2_5 = A.sum(0) 
    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                if input_oh_demand[week_i, day_i, hour_i] == 0:
                    constraints.append(X_2_5[week_i, day_i, hour_i] == 0)

    # ---------------- Soft Constraints (CP objective) ----------------

    # 3.1: Minimize Maximum-Weekly-Hour
    X = A.sum((2, 3)) # shape: (# of staff, # of remaining weeks)
    T = input_target_weekly_hours[:, None].repeat(n, axis=1)
    X_minus_T = X - T
    T_minus_X = T - X

    # Apply maximum on each variable with 0
    term_3_1 = 0
    for staff_i in range(m):
        for week_i in range(n):
            term_3_1 += cp.maximum(X_minus_T[staff_i, week_i], 0)
            term_3_1 += cp.maximum(T_minus_X[staff_i, week_i], 0)


    # 3.2 (w/o QC): Minimize Total Future Hour Violations Per Staff
    X = A.sum((1, 2, 3)) # shape: (num staff, )
    term_3_2 = 0
    for staff_i in range(m):
        term_3_2 += cp.maximum(X[staff_i] - input_target_total_future_hours[staff_i], 0)

    # 3.3 (w/o QC): Minimize Total # of violations where we've assigned too few people in a slot
    X = A.sum(0)

    term_3_3 = 0
    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                term_3_3 += cp.maximum(input_oh_demand[week_i, day_i, hour_i] - X[week_i, day_i, hour_i], 0)
                term_3_3 += cp.maximum(X[week_i, day_i, hour_i] - input_oh_demand[week_i, day_i, hour_i], 0)


    # 3.4: Scheduling Assignment Displeasure

    staff_availabilities_extended = input_staff_availabilities[:, None, :, :].repeat(n, axis=1)

    apply_mapping = np.vectorize(lambda val: RATE_TO_DISPLEASURE_MAPPING[val])
    mapped_staff_availabilities_extended = apply_mapping(staff_availabilities_extended)

    multiplied = A * mapped_staff_availabilities_extended
    term_3_4 = np.sum(multiplied)


    # 3.5: Consistent Weekly Hours (w/o MIQP)
    current_week = A[:, 0, :, :] # shape: (# of staff, 5, 12)


    # Assuming input_previous_weeks_assignments[0] is the first week the OH scheduler ran
    term_3_5 = 0
    # Match current week with the past
    if p:
        prev_weeks_weights = list(reversed(list(map(lambda_func, np.arange(1, p + 1)))))

        for prev_i in range(p):
            
            for staff_i in range(m_day_ones):
                for day_i in range(5):
                    for hour_i in range(12):
                        term_3_5 += cp.maximum(input_previous_weeks_assignments[staff_i, prev_i, day_i, hour_i] - \
                                            current_week[staff_i, day_i, hour_i], 0) * \
                                            prev_weeks_weights[prev_i] * \
                                            (1 - input_changed_hours_weightings[staff_i])
                                           

    # Match current week with future weeks
    future_weeks_weights = list(map(lambda_func, np.arange(1, n + 1)))
    for future_i in range(1, n):
        
        for staff_i in range(m_day_ones):
            for day_i in range(5):
                for hour_i in range(12):
                    term_3_5 += cp.maximum(current_week[staff_i, day_i, hour_i] - A[staff_i, future_i, day_i, hour_i], 0) * future_weeks_weights[future_i]


    obj = cp.Minimize(U_3_1 * term_3_1 + U_3_2 * term_3_2 + U_3_3 * term_3_3 + U_3_4 * term_3_4 + U_3_5 * term_3_5)


    # Optimization Problem
    print(f"Number of variables: {m * n * 5 * 12}")
    print(f"Number of constraints: {len(constraints)}")

    print("Running algorithm...")
    start = perf_counter()
    prob = Problem(obj, constraints)
    prob.solve(verbose=False)
    print(f"Algorithm status: {prob.status}. Objective value: {prob.value}")
    print(f"Time elapsed: {perf_counter() - start}")

    all_assignments = var_to_np(A)

    np.save("assignments.npy", all_assignments)

    return all_assignments[:, 0, :, :]

from cvxpy import *
import numpy as np
import cvxpy as cp
import warnings
from time import perf_counter
import threading
import sys
import time
import logging
import builtins

from . import paths

warnings.filterwarnings(
    "ignore",
    message="Objective contains too many subexpressions.*",
    category=UserWarning,
)

# Defining weights
U_3_1 = 400 #Minimize Maximum-Weekly-Hour
U_3_2 = 50  # 3.2 (w/o QC): Minimize Total Future Hour Violations Per Staff
U_3_3 = 700 #(w/o QC): Minimize Total # of violations where we've assigned too few people in a slot
U_3_4 = 50 #Scheduling Assignment Displeasure
U_3_5 = 50   #consistency constraint

# Weight fxn used in term 3.5 (consistent weekly hours)
lambda_func = lambda x: np.exp(-0.2 * x)

# Mapping between rating and displeasure used in term 3.4 (minimize displeasure)
RATE_TO_DISPLEASURE_MAPPING = {1: 0, 2: 2, 3: 8, 4: 16, 5: 1e8}


PROGRESS_BASE_SECONDS = 20


def progress_indicator(message: str, stop_event: threading.Event, total_duration: float = PROGRESS_BASE_SECONDS, bar_length: int = 32) -> None:
    """Display an animated progress bar until stop_event is set."""
    bar_length = builtins.max(bar_length, 1)
    position = 0
    stream = sys.__stdout__
    interval = builtins.max(total_duration / bar_length, 0.1)
    while not stop_event.is_set():
        filled = position % (bar_length + 1)
        bar = "#" * filled + "-" * (bar_length - filled)
        stream.write(f"\r{message} [{bar}]")
        stream.flush()
        time.sleep(interval)
        position = (position + 1) % (bar_length + 1)
    stream.write(f"\r{message} [{'#' * bar_length}]")
    stream.flush()
    time.sleep(interval)
    stream.write("\r" + " " * (len(message) + bar_length + 3) + "\r")
    stream.flush()


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

def run_algorithm(inputs, expected_duration: float = PROGRESS_BASE_SECONDS):
    logger = logging.getLogger(__name__)

    input_oh_demand = inputs[0]                         # (# of future weeks, 5, 12)
    input_previous_weeks_assignments = inputs[1]        # (# of day one staff, # of past weeks, 5, 12)
    input_staff_availabilities = inputs[2]              # (# of all staff, 5, 12)
    input_max_contig = inputs[3]                        # (# of all staff, )
    input_target_total_future_hours = inputs[4]         # (# of all staff, )
    input_target_weekly_hours = inputs[5]               # (# of all staff, )
    input_preferred_contiguous_hours = inputs[6]        # (# of all staff, )
    input_changed_hours_weightings = inputs[7]          # (# of day one staff, )
    input_non_day_one_indices = inputs[8]               # (# of non day one staff, )

    logger.debug("Previous assignments tensor shape: %s", getattr(input_previous_weeks_assignments, "shape", None))
    m = input_max_contig.shape[0]
    m_non_day_ones = input_non_day_one_indices.shape[0] # WARNING: assumes non-day one staff are 
                                                        # added to the end of each prev_assignments array
    m_day_ones = m - m_non_day_ones

    n = input_oh_demand.shape[0]
    
    try:
        p = input_previous_weeks_assignments.shape[1] # TODO: change later, but we probably don't want to perform look-behind for all prev weeks, fixed look behind sliding window keeps computational complexity down with minimal resulting tradeoff
        logger.debug("Using last %s week(s) of assignments for consistency constraints.", p)
    except IndexError:
        p = None
        logger.debug("No historical assignments available; skipping consistency constraint.")

    # Define the decision variable
    A = np.empty(shape = (m, n, 5, 12), dtype = object)
    for i in range(m): # m TAs?
        for j in range(n): # OH Demand ?
            for k in range(5): # 5 days
                for l in range(12): # 12 hours per ay
                    A[i, j, k, l] = cp.Variable(boolean=True)
    logger.debug("Decision variables initialised for %s staff across %s future weeks.", m, n)

    
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

    # 2.3 (TESTING) no timeslot should have > 3 number of absences
    X_2_3 = np.sum(A, axis=0)

    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                constraints.append(input_oh_demand[week_i, day_i, hour_i] - X_2_3[week_i, day_i, hour_i] <= 3)

    # 2.4 (TEMP/TESTING) no one should be doing >3+ their target weekly hours
    X_2_4 = A.sum((2, 3))
    weekly_targets = input_target_weekly_hours.astype(float)
    T = weekly_targets[:, None].repeat(n, axis=1)

    for staff_i in range(m):
        for week_i in range(n):
            if weekly_targets[staff_i] <= 0:
                constraints.append(X_2_4[staff_i, week_i] == 0)
            else:
                constraints.append(X_2_4[staff_i, week_i] - T[staff_i, week_i] <= 1)

    # 2.5 (TEMP/TESTING) no assignments during times of 0 demand
    X_2_5 = A.sum(0) 
    for week_i in range(n):
        for day_i in range(5):
            for hour_i in range(12):
                if input_oh_demand[week_i, day_i, hour_i] == 0:
                    constraints.append(X_2_5[week_i, day_i, hour_i] == 0)


    # 2.6 (TEMP/TESTING) ensure no one gets assigned to a slot they are unavailable for TODO
    

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
                # if a staff member doesn't work for a week, then skip them for that week
                if input_previous_weeks_assignments[staff_i, prev_i].sum() == 0:
                    continue

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

    total_variables = m * n * 5 * 12
    logger.info("Optimisation problem: %s variables, %s constraints.", total_variables, len(constraints))

    solve_stop = threading.Event()
    duration = builtins.max(expected_duration, 1.0)
    solve_thread = threading.Thread(
        target=progress_indicator,
        args=("Solving optimisation (this may take a few minutes)...", solve_stop, duration),
        daemon=True,
    )
    solve_thread.start()

    start = perf_counter()
    prob = Problem(obj, constraints)

    prob.solve(verbose=False, solver=cp.SCIPY, scipy_options={"disp": False})

    solve_stop.set()
    solve_thread.join()
    stream = sys.__stdout__
    stream.write("\rSolving optimisation complete.\n")
    stream.flush()

    elapsed = perf_counter() - start

    stats = getattr(prob, "solver_stats", None)
    if stats is not None:
        logger.debug("Solver stats: %s", stats)

    logger.info("Solver status: %s | objective: %.4f | elapsed: %.2fs", prob.status, prob.value, elapsed)

    all_assignments = var_to_np(A)
    paths.ensure_directories()
    assignment_path = paths.NPY_DIR / "assignments.npy"
    np.save(assignment_path, all_assignments)
    logger.debug("Saved assignment tensor to %s", assignment_path)

    return all_assignments[:, 0, :, :]

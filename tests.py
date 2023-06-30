import json
import utils
import State
from config_read import *
import os
import shutil
import numpy as np

sheets = ["https://docs.google.com/spreadsheets/d/1zL-lB4KNGmGz-CMAuAb8c_UBtlanwRVad-rN6ZOrtMg/edit#gid=1765561727", 
          "https://docs.google.com/spreadsheets/d/1Z0aTQPV5fS-iwhV7lWy74ocQmawtT1tpEGh1qWC6Zro/edit#gid=1765561727",
          "https://docs.google.com/spreadsheets/d/1AEeEHHfzG3ov8oyxLvWTjfcukOHN2ut8TsbOh1INyLA/edit#gid=1765561727"]

def create_new_state(sheet):
    config = read_config("config.json")
    availabilities_id = get_google_sheets_id(sheet)
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)

    demand_id = get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])

    latest_week = utils.get_latest_week(config.get("path_to_bucket"))
    if latest_week > -1:
        last_state = utils.deserialize(config.get("path_to_bucket"), latest_week, config["weeks_skipped"])
    else:
        last_state = None

    state = State.state(last_state, demand, availabilities, config["class"], config["semester"], config["weeks"], config["weekly_hour_multiplier"], config["weeks_skipped"])
    state.serialize(config.get("path_to_bucket"))
    return state

def delete_folder_contents(folder_path):
    """Deletes all files and subdirectories within the specified folder.

    Args:
        folder_path (str): Path to the folder to be cleared.
    """
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)

def check_deserialize():
    config = read_config("config.json")
    latest_week = utils.get_latest_week(config.get("path_to_bucket"))
    if latest_week > -1:
        last_state = utils.deserialize(config.get("path_to_bucket"), latest_week, config["weeks_skipped"])
        print(last_state)
        last_state.print_algo_outputs()
    else:
        print("No state found")
        
def basic_test():
    config = read_config("config.json")
    delete_folder_contents(config.get("path_to_bucket"))
    states = []
    for sheet in sheets:
        state = create_new_state(sheet)
        state.set_assignments(generate_dummy_assignments(len(state.StaffMember_dict)))
        state.serialize(config.get("path_to_bucket"))
        states.append(state)
    print("######### FIRST STATE #########")
    print(states[0])
    states[0].print_algo_outputs()
    print("######### SECOND STATE #########")
    print(states[1])
    states[1].print_algo_outputs()
    print("######### THIRD STATE #########")
    print(states[2])
    states[2].print_algo_outputs()

def generate_dummy_assignments(staff_number):
    assignments = []
    for i in range(staff_number):
        array = np.zeros((5, 12), dtype=int)
    
        for i in range(5):
            ones_indices = np.random.choice(12, 3, replace=False)
            array[i, ones_indices] = 1
        
        assignments.append(array)
    assignments = np.array(assignments)
    return assignments
    

if __name__ == '__main__':
    basic_test()
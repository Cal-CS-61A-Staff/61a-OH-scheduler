import json
import utils
import State
from config_read import *
import os
import shutil
import numpy as np
import config_read
import validation

sheets = ["https://docs.google.com/spreadsheets/d/1zL-lB4KNGmGz-CMAuAb8c_UBtlanwRVad-rN6ZOrtMg/edit#gid=1765561727", 
          "https://docs.google.com/spreadsheets/d/1Z0aTQPV5fS-iwhV7lWy74ocQmawtT1tpEGh1qWC6Zro/edit#gid=1765561727",
          "https://docs.google.com/spreadsheets/d/1AEeEHHfzG3ov8oyxLvWTjfcukOHN2ut8TsbOh1INyLA/edit#gid=1765561727"]

AVAILABILITIES_RANGE = 'Form Responses 1!B1:BP'
DEMAND_RANGE = 'Demand!A2:E'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# def delete_files_with_prefix(project_id, bucket_name, prefix):
#     # Create a client object for interacting with the Google Cloud Storage API
#     client = storage.Client(project=project_id)
    
#     # Get the bucket object
#     bucket = client.get_bucket(bucket_name)
    
#     # List all the files in the bucket with the given prefix
#     blobs = bucket.list_blobs(prefix=prefix)
    
#     # Delete each file with the specified prefix
#     for blob in blobs:
#         blob.delete()
    
#     print(f"All files with prefix '{prefix}' have been deleted from the bucket '{bucket_name}'.")
        
def basic_test():
    """Tests for 2 students who only have 3 slots available every week, which never changes, that matches up perfectly with OH_demand.
    """
    config = config_read.read_config("tests/basic_test.json")
    validation.validate_config(config)
    prefix = f"{config['class']}-{config['semester']}"
    
    # get spreadsheets
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validation.validate_availabilities(availabilities)

    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])
    # already validates OH demand in get_demand. Could add more validation here if needed

    delete_files_with_prefix(config["project_id"], config["bucket_name"], prefix)

    last_state = None
    for i in range(config["weeks"] - config["weeks_skipped"]):
        state = State.State(last_state, 
                        demand, 
                        availabilities, 
                        config["class"], 
                        config["semester"], 
                        config["weeks"], 
                        config["weekly_hour_multiplier"], 
                        config["weeks_skipped"])
        inputs = state.get_algo_inputs()
        assignments = run_algorithm(inputs)
        state.set_assignments(assignments)
        last_state = state
    
    current = state
    while current:
        print(f"week {current.week_num} assignments:")
        for email in current.course_staff_dict:
            index = current.bi_mappings[email]
            print(f"user {email}'s assignments are:")
            print(current.course_staff_dict[email].assigned_hours)
            print("\n\n\n")
        print(f"week {current.week_num} inputs:")
        current.print_algo_outputs()
        print("\n\n\n")
        current = current.prev_state

    state.serialize(config["project_id"], config["bucket_name"], prefix)

def run_algorithm(inputs):
    # Placeholder
    course_size = inputs[2].shape[0]
    ans = []
    for i in range(course_size):
        assignments = np.zeros((5, 12))
        hours_target = inputs[5][i]
        indices = np.random.choice(range(60), hours_target, replace=False)
        assignments.flat[indices] = 1
        ans.append(assignments)
    ans = np.array(ans)
    if len(ans) > 1:
        ans = np.stack(ans)
    return ans

if __name__ == '__main__':
    basic_test()
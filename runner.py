import config_read
import send_email
import utils
import State
import tests 
import os
import numpy as np
import shutil
from datetime import timedelta
import re
from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound
import validation

# The range of both spreadsheet. This should not change unless the forms/the demand spreadsheet has been edited.
AVAILABILITIES_RANGE = 'Form Responses 1!B1:BP'
DEMAND_RANGE = 'Demand!A2:E'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"


def main():
    # Config Read
    config = config_read.read_config("config.json")
    validation.validate_config(config)
    
    # Get availabilities data
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validation.validate_availabilities(availabilities)

    # Get OH demand data
    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])

    # Get last state
    prefix = f"{config['class']}-{config['semester']}"
    latest_week = utils.get_latest_week(config["project_id"], config["bucket_name"], prefix)
    if latest_week > -1:
        last_state = utils.deserialize(config.get("project_id"), config["bucket_name"], latest_week, config["weeks_skipped"], prefix)
    else:
        last_state = None

    if latest_week == config['weeks']:
        raise RuntimeError("Allotted # of weeks have already passed. Exiting.")

    # create new state
    state = State.state(last_state, 
                        demand, 
                        availabilities, 
                        config["class"], 
                        config["semester"], 
                        config["weeks"], 
                        config["weekly_hour_multiplier"], 
                        config["weeks_skipped"])
    
    # run algorithm
    # inputs = state.get_algo_inputs()
    # assignments = run_algorithm(inputs)
    # state.set_assignments(assignments)

    # validate algorithm outputs
    
    # send emails
    # mappings = state.bi_mappings
    # first_monday = utils.nearest_future_monday(config["start_date"])
    # starting_monday = first_monday + timedelta((state.week_num - config["weeks_skipped"] - 1)* 7)
    # for i in range(assignments.shape[0]):
    #     email = mappings.inverse[i]
    #     send_email.send_invites(email, 
    #                           assignments[i], 
    #                           starting_monday, 
    #                           config["calendar_event_name"], 
    #                           config["calendar_event_location"], 
    #                           config["calendar_event_description"])
    
    # state.serialize(config["project_id"], config["bucket_name"], prefix)



def run_algorithm(inputs):
    # Placeholder
    course_size = inputs[2].shape[0]
    ans = []
    for i in range(course_size):
        assignments = np.zeros((5, 12))
        hours_target = inputs[3][i]
        indices = np.random.choice(range(60), hours_target, replace=False)
        assignments.flat[indices] = 1
        ans.append(assignments)
    ans = np.array(ans)
    if len(ans) > 1:
        ans = np.stack(ans)
    return ans

if __name__ == '__main__':
    main()
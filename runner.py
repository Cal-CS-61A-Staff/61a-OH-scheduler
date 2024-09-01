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
#from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound
import validation
import algorithm
import pandas as pd

# The range of both spreadsheet. This should not change unless the forms/the demand spreadsheet has been edited.
AVAILABILITIES_RANGE = 'Form Responses 1!B1:BQ'
DEMAND_RANGE = 'Demand!A2:E'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"


def main():
    # Config Read
    config = config_read.read_config("key.json")
    validation.validate_config(config)

    # Get availabilities data
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validation.validate_availabilities(availabilities)

    # Get OH demand data
    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])

    # Get last state
    prefix = f"{config['class']}-{config['semester']}/"
    latest_week = utils.get_latest_week(config["project_id"], config["bucket_name"], prefix)
    if latest_week > -1:
        last_state = utils.deserialize(config.get("project_id"), config["bucket_name"], latest_week, config["weeks_skipped"], prefix)
    else:
        last_state = None
    
    if last_state and last_state.week_num == config["weeks"]:
        print(f"ERROR: The algorithm has already been run for all weeks. The last state was for week {config['weeks']}. Exiting.")
        return

    if latest_week == config['weeks']:
        raise RuntimeError("Allotted # of weeks have already passed. Exiting.")

    # Create new state object
    state = State.State(last_state, 
                        demand, 
                        availabilities, 
                        config["class"], 
                        config["semester"], 
                        config["weeks"], 
                        config["weekly_hour_multiplier"], 
                        config["weeks_skipped"])
    
    # Run algorithm
    inputs = state.get_algo_inputs()
    assignments = algorithm.run_algorithm(inputs)
    # assignments = np.load("assignments.npy")[:, 0, :, :]

    np.save('demand.npy', demand)

    state.set_assignments(assignments)

    print()
    # Create CSV export of the next week's assignments
    export_dict = {"email": [], "hours_assigned": []}
    for i in range(assignments.shape[0]):
        if assignments[i].sum() != 0:

            export_dict['email'].append(state.bi_mappings.inverse[i])
            export_dict['hours_assigned'].append(assignments[i].sum())

    export_df = pd.DataFrame(data=export_dict)
    export_df.to_csv("hours_assigned.csv", index=False)

    # Validate algorithm output TODO

    # Email send
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

if __name__ == '__main__':
    main()

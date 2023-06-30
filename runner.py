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

# The range of both spreadsheet. This should not change unless the forms/the demand spreadsheet has been edited.
AVAILABILITIES_RANGE = 'Form Responses 1!B1:BP'
DEMAND_RANGE = 'Demand!A2:E'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

def validate_config(config):
    """Validates that config.json has all the required fields and that the values are valid

    Args:
        config (dictionary): output of config_read
    """
    for key in config:
        if not config[key]:
            raise ValueError(f"Config field {key} is empty")
        
    # check if google project exists and if we have permission
    client = storage.Client(project=config["project_id"])
    
    # check if bucket exists and we have permission
    try:
        bucket = client.bucket(config["bucket_name"])
        if not bucket.exists():
            print(f"Bucket {config['bucket_name']} does not exist in the project: {config['project_id']}")
            return False
        return True
    except Forbidden:
        print(f"No access to the bucket {config['bucket_name']} in the project: {config['project_id']}")
        return False
    
    if config["weekly_hour_multiplier"] < 1:
        raise ValueError("Weekly hour multiplier must be at least 1")
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, config["start_date"]):
        raise ValueError("start_date is not in the 'YYYY-MM-DD' format.")
    
    if config["weeks_skipped"] < 0:
        raise ValueError("Weeks skipped must be at least 0")
    
    if config["weeks_skipped"] >= config["weeks"]:
        raise ValueError("Weeks skipped must be less than the total number of weeks")
    


def validate_availabilities(sheet):
    # check each row
    for row in sheet:
        email = row[State.course_staff.email_address_index]
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if (re.match(pattern, email) is None):
            raise ValueError(f"Invalid email: {email}")
        
        total_hours = row[State.course_staff.total_weekly_hours_index]
        target_weekly_hours = row[State.course_staff.weekly_oh_hours_index]
        preferred_contiguous_hours = row[State.course_staff.preferred_contiguous_hours_index]

        if target_weekly_hours > total_hours:
            raise ValueError(f"Target hours ({target_weekly_hours}) cannot be greater than total hours ({total_hours}) for email {email}")
        
        if preferred_contiguous_hours > target_weekly_hours:
            raise ValueError(f"Preferred hours ({preferred_contiguous_hours}) cannot be greater than target hours ({target_hours}) for email {email}")
        
        not_availables = 0
        for i in State.course_staff.availabilities_indices:
            if row[i] < 1 or row[i] > 5:
                raise ValueError(f"Invalid availability for email {email}. Must start with a number between 1 and 5")
            if row[i] == 5:
                not_availables += 1

        if (5 * 12 - not_availables) < target_weekly_hours:
            print(f"Warning: email {email} has less than {target_weekly_hours} available hours")
    

def main():
    config = config_read.read_config("config.json")
    validate_config(config)
    prefix = f"{config['class']}-{config['semester']}"
    
    # get spreadsheets
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validate_availabilities(availabilities)

    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])
    # already validates OH demand in get_demand. Could add more validation here if needed

    # get last state
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
import State
import re
import config_read
import utils, os
#from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound

CONFIG_KEYS = [
    "demand_link",
    "availabilities_link",
    "project_id",
    "bucket_name",
    "class",
    "semester",
    "weeks",
    "weekly_hour_multiplier",
    "start_date",
    "weeks_skipped",
    "calendar_event_name",
    "calendar_event_location",
    "calendar_event_description"
]
# The range of both spreadsheet. This should not change unless the forms/the demand spreadsheet has been edited.
AVAILABILITIES_RANGE = 'Form Responses 1!B1:BQ'
DEMAND_RANGE = 'Demand!A2:E'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

def test():
    config = config_read.read_config("config.json")
    validate_config(config)
    # Get availabilities data
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validate_availabilities(availabilities)
    print(availabilities)
    validate_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(validate_id, DEMAND_RANGE, config["weeks"])
    print(demand)
    print("Validation passed!")
    # validation test!


def validate_config(config):
    """Validates that config.json has all the required fields and that the values are valid

    Args:
        config (dictionary): output of config_read

    Returns:
        None
    """
    
    # Check each key has a corresponding value
    for key in config:
        if config[key] is None:
            raise ValueError(f"Config field {key} is empty")
        
    # Check if google project exists and if we have permission
    # client = storage.Client(project=config["project_id"])
    
    # # Check if bucket exists and we have permission
    # try:
    #     bucket = client.bucket(config["bucket_name"])
    #     if not bucket.exists():
    #         raise NotFound(f"Bucket {config['bucket_name']} does not exist in the project: {config['project_id']}")
    # except Forbidden:
    #     raise Forbidden(f"No access to the bucket {config['bucket_name']} in the project: {config['project_id']}")
    
    
    if config["weekly_hour_multiplier"] < 1:
        raise ValueError("Weekly hour multiplier must be at least 1")
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, config["start_date"]):
        raise ValueError("start_date is not in the 'YYYY-MM-DD' format.")
    
    if config["weeks_skipped"] < 0:
        raise ValueError("Weeks skipped must be at least 0")
    
    if config["weeks_skipped"] >= config["weeks"]:
        raise ValueError("Weeks skipped must be less than the total number of weeks")
    
    # Make sure all keys are in dictionary
    assert set(CONFIG_KEYS) - set(config.keys()) == set(), f"config.json is missing the following keys: {set(CONFIG_KEYS) - set(config.keys())}"

def validate_availabilities(sheet):
    """Validates that the availabilities sheet has all the required fields and that the values are valid

    Args:
        sheet (list): output of config_read

    Returns:
        None
    """
    #print(sheet)
    for row in sheet:
        #print(f'row: {row}')
        email = row[State.StaffMember.EMAIL_ADDRESS_INDEX]

        # Check if email is valid
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if (re.match(pattern, email) is None):
            raise ValueError(f"Invalid email: {email}")
        
        total_hours = row[State.StaffMember.TOTAL_WEEKLY_HOURS_INDEX]
        target_weekly_hours = row[State.StaffMember.WEEKLY_OH_HOURS_INDEX]
        preferred_contiguous_hours = row[State.StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX]

        if target_weekly_hours > total_hours:
            raise ValueError(f"Target hours ({target_weekly_hours}) cannot be greater than total hours ({total_hours}) for {email}")
        
        if preferred_contiguous_hours > target_weekly_hours:
            raise ValueError(f"Preferred hours ({preferred_contiguous_hours}) cannot be greater than target hours ({target_weekly_hours}) for {email}")
        
        # Check total availabilities
        num_not_available = 0
        for i in State.StaffMember.AVAILABILITIES_INDICES:
            if row[i] < 1 or row[i] > 5:
                raise ValueError(f"Invalid availability for email {email}. Must start with a number between 1 and 5")
            if row[i] == 5:
                num_not_available += 1

        if (5 * 12 - num_not_available) < target_weekly_hours:
            raise ValueError(f"Email {email} has less than {target_weekly_hours} available hours")


# if __name__ == main():
#     main()


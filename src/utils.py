from __future__ import print_function

import os.path
import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pickle
from bidict import bidict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import config_read
from . import paths
from . import state as state_module


class _StateUnpickler(pickle.Unpickler):
    """Custom unpickler that maps legacy module names to the current package layout."""

    _MODULE_RENAMES = {
        "State": "src.state",
        "utils": "src.utils",
        "config_read": "src.config_read",
        "validation": "src.validation",
    }

    def find_class(self, module, name):
        module = self._MODULE_RENAMES.get(module, module)
        return super().find_class(module, name)


def _load_compat_pickle(file_obj):
    """Load pickle data while remapping legacy module paths."""
    return _StateUnpickler(file_obj).load()

# Service Account Scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly',
         'https://www.googleapis.com/auth/calendar']


def get_sheet_values(spread_sheet_id, range):
    """ Reads items from a google sheet.

    Args:
        spread_sheet_id (string): ID of the google sheet to read from.
        range (string): google sheet range string to read from

    Returns:
       list: Returns a list of lists, where each list is a row in the sheet. The first row is the header row.
    """

    # Creating credentials
    try:
        creds = service_account.Credentials.from_service_account_file(
            str(paths.CREDS_DIR / "credentials.json"), scopes=SCOPES
        )
    except FileNotFoundError:
        print("Error: credentials.json not found. \nFollow instructions in README.md to get your credentials.json key and place it in the credentials/ folder!!")
        exit(1)  

    service = build('sheets', 'v4', credentials = creds)

    # Calling the Sheets API for values in the spreadsheet
    sheet = service.spreadsheets()
    try:
        result = sheet.values().get(spreadsheetId=spread_sheet_id, range=range).execute()
    except HttpError as e:
        print(f"Error: {e}")
        print("(Did you remember to share the google sheet with the service account email?\nTry checking the list of users each sheet is shared with.)")
        exit(1)
    values = result.get('values', [])

    return values

def get_demand(sheet_id, range, total_weeks):
    """
    Gets the demand for OH from the spreadsheet, for every week. There should be a row for
    every single week from 1 -> total weeks (inclusive on both ends). If there isn't, this errors.

    Args:
        sheet_id (string): google sheet ID to read from
        range (string): range to read from
        total_weeks (int): total number of weeks in instruction

    Raises:
        Exception: No OH demand was found for this link/range

    Returns:
        np_array: OH demand. Shape: (total_weeks, days, times)
    """
    values = get_sheet_values(sheet_id, range)

    #print(values)

    if values == [[]]:
        raise Exception('No OH demand information found.')
    
    output = np.full((total_weeks, 5, 12), -1)
    weekday_mapping = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}
    hours_mapping = {"9:00 AM": 0, "10:00 AM": 1, "11:00 AM": 2, "12:00 PM": 3, "1:00 PM": 4, "2:00 PM": 5, "3:00 PM": 6, "4:00 PM": 7, "5:00 PM": 8, "6:00 PM": 9, "7:00 PM": 10, "8:00 PM": 11}
    next_hour_validation = {"9:00 AM": "10:00 AM", "10:00 AM": "11:00 AM", "11:00 AM": "12:00 PM", "12:00 PM": "1:00 PM", "1:00 PM": "2:00 PM", "2:00 PM": "3:00 PM", "3:00 PM": "4:00 PM", "4:00 PM": "5:00 PM", "5:00 PM": "6:00 PM", "6:00 PM": "7:00 PM", "7:00 PM": "8:00 PM", "8:00 PM": "9:00 PM"}

    for row in values:
        if row[0]: # Ensure merged cells (empty cells after merged value) use the correct week
            weeks_str = row[0]
            valid_week = re.compile(r"([0-9]+)||([0-9]+, )+")

            if not valid_week.match(weeks_str):
                raise ValueError(f"Error: {weeks_str} is not in the correct format (e.g. 2, 3, 4).")
            week_indices = [int(week) for week in weeks_str.split(", ")]
        
        if row[1]: # Ensure merged cells (empty cells after merged value) use the correct day
            day = row[1]
            valid_day = re.compile(r"(Monday)||(Tuesday)||(Wednesday)||(Thursday)||(Friday)")
            if not valid_day.match(day):
                raise ValueError(f"Error: {day} is not in the correct format (e.g. Monday, Tuesday).")
            day_index = weekday_mapping[day]
        
        if not row[2]:
            raise ValueError(f"Error: {row[2]} doesn't exist. Must be a string for an hour between 9:00 AM and 8:00 PM.")
        
        if not row[3]:
            raise ValueError(f"Error: {row[3]} doesn't exist. Must be a string for an hour between 10:00 AM and 9:00 PM.")
        
        starting_hour = row[2]
        ending_hour = row[3]
        valid_hour = re.compile(r"([0-9]+:00 [AP]M)")

        if not (valid_hour.match(starting_hour) and valid_hour.match(ending_hour)):
            raise ValueError(f"Error: time inputs for row {row} are wrong. Must be a string for an hour between 9:00 AM and 9:00 PM.")
        
        if starting_hour not in hours_mapping.keys():
            raise ValueError(f"Error: starting time for row {row} is invalid. Must be 9:00 AM to 8:00 PM.")
        
        if ending_hour != next_hour_validation[starting_hour]:
            raise ValueError(f"Error: ending time for row {row} is invalid. Must be 1 hour after starting hour.")
        
        hour_index = hours_mapping[starting_hour]

        num_staff = row[4]
        valid_num_staff = re.compile(r"[0-9]+")
        if not valid_num_staff.match(num_staff):
            print(f"Error: {num_staff} is not in the correct format (int).")
            return
        
        for week_index in week_indices:
            if week_index < 1 or week_index > total_weeks:
                raise ValueError(f"Error: Week {week_index} is not a valid week. Must be between 1 and total_weeks ({total_weeks}) (inclusive).")
            if output[week_index - 1][day_index][hour_index] != -1:
                raise ValueError(f"Error: Week {week_index}, {day} {starting_hour} is already filled. Is there a duplicate week/day/hour?")
            output[week_index - 1][day_index][hour_index] = int(num_staff)

    if np.any(output == -1):
        raise ValueError("Invalid array. Some values were not filled. Ensure that there is an entry in the oh demand spreadsheet has for every week from 1 to total weeks, " + \
                         "for each day, and for all hours 9:00 AM to 9:00 PM, and that there are no duplicate weeks/days/hours.")
    return output

def get_availabilities(sheet_id, range):
    """
    Gets a list of lists representing each course staff in the availabilities spreadsheet.

    Args:
        sheet_id (string): ID of the google sheet to read from. 
        range (string): google sheets range string to read from
        
    Returns:
        values (list): list of lists each representing a row in the sheet.
    """
    # Create sheet object and get all values
    values = get_sheet_values(sheet_id, range)
    if not values:
        raise Exception('No staff availabilities data found.')
    
    rows = values[1:] # change to [0:] if you don't want to skip the header row
    rows_dict = {}  # Dictionary to store rows by email, to avoid duplication
    edited_rows = []  # List to store the final ordered rows without duplicates

    print("pulling staff member availabilities... (using the utils.get_availabilities() function)")
    for row in rows:
        email = row[state_module.StaffMember.EMAIL_ADDRESS_INDEX]

        # Let's go through the spreadsheet and convert everything into a number we can actually use
        row[state_module.StaffMember.TOTAL_WEEKLY_HOURS_INDEX] = int(row[state_module.StaffMember.TOTAL_WEEKLY_HOURS_INDEX])
        row[state_module.StaffMember.SEMESTERS_ON_STAFF_INDEX] = int(row[state_module.StaffMember.SEMESTERS_ON_STAFF_INDEX])
        row[state_module.StaffMember.SEMESTER_AS_AI_INDEX] = int(row[state_module.StaffMember.SEMESTER_AS_AI_INDEX])
        

        #GET WEEKLY OH HOURS
        # some people put weird things in this column like "n/a" which is not a number therefore the bane of our existence
        try:
            row[state_module.StaffMember.WEEKLY_OH_HOURS_INDEX] = int(row[state_module.StaffMember.WEEKLY_OH_HOURS_INDEX])
        except:
            row[state_module.StaffMember.WEEKLY_OH_HOURS_INDEX] = 4 #default to 4

         #GET CONTIGUOUS HOURS
         # sometimes people put a range of contiguous hours and this is not a number therefore the bane of our existence
        try: 
            row[state_module.StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX] = int(row[state_module.StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX].split(" ")[0])
        except:
            row[state_module.StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX] = 2 #Default to 2
        
        
        # For debugging below...
        # time = ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM', '5PM', '6PM', '7PM', '8PM', '9PM']
        # days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


        #GET AVAILABILITIES
        for i in state_module.StaffMember.AVAILABILITIES_INDICES:

            try:    
                row[i] = int(row[i])
            except:
                # because some of the values are like "1 - I'd love this time", lets grab the first number.
                row[i] = int(row[i].split(" ")[0]) 

            # Adjust the index for time and day
            availability_index = i - 8  # Shift the index to start at 0 for availability
            hour_index = availability_index % 12  # Get the hour index (0 to 11)
            day_index = availability_index // 12  # Get the day index (0 to 4)

            # Print time, day, and availability (for debugging)
            #print(f"{time[hour_index]} {days_of_week[day_index]} Availability: {row[i]}")
        

        # Check if this data is a duplicate
        if email in rows_dict:
            print(f"ALERT: found duplicate for {email}. Replacing previous data with updated availability.")
            # Replace the previous row in final_rows with the new row
            for index, existing_row in enumerate(edited_rows):
                if existing_row[0] == email:
                    edited_rows[index] = row
                    break
        else:
            # this data is new, not a duplicate. add row to both the dictionary and edited row list
            rows_dict[email] = row
            edited_rows.append(row)


    print(f"Loaded {len(edited_rows)} staff availabilities (removed {len(rows) - len(edited_rows)} duplicates).")

    return edited_rows

def create_5x12_np_array(input_list):
    """
    This function takes a list of 60 numbers, validates that the list contains exactly 60 elements and
    each element is a number from 1 to 5. It then creates a 5x12 numpy array from the list.

    Args:
        input_list (list): A list of integers, each of which is a number from 1 to 5.

    Returns:
        array (numpy.ndarray): A 5x12 numpy array created from the input list.

    Raises:
        ValueError: If the input list does not contain exactly 60 elements.
        ValueError: If any element in the input list is not an integer between 1 and 5.
    """

    # Check that the length of the list is 60
    if len(input_list) != 60:
        raise ValueError('Input list must contain exactly 60 elements.')

    # Check that each value is an integer between 1 and 5
    for value in input_list:
        if not isinstance(value, int) or value < 1 or value > 5:
            raise ValueError('All elements in input list must be an integer between 1 and 5.')

    # Convert the list into a 1D numpy array
    array = np.array(input_list)
    
    # Reshape the array into a 5x12 numpy array
    array = array.reshape((5, 12))

    return array

def doubly_mapped_dictionary(input_dict):
    """
    This function takes a dictionary as input and creates a new dictionary 
    where each key-value pair is duplicated with the value becoming a key and the key becoming a value.

    Args:
        input_dict (dict): The dictionary to be processed.

    Returns:
        output_dict (dict): A new dictionary where each key-value pair from the input dictionary 
        has been duplicated with the value becoming a key and the key becoming a value.

    Raises:
        ValueError: If the values in the input dictionary are not hashable, 
        and hence can't be used as keys in a dictionary.
    """
    # Copy the original dictionary
    output_dict = input_dict.copy()

    # Iterate over the input dictionary and add the reversed mappings
    for key, value in input_dict.items():
        if not isinstance(value, (int, float, str, bool, tuple)):
            raise ValueError('Values in the input dictionary must be hashable (i.e., immutable).')

        output_dict[value] = key

    return output_dict

def get_latest_week(project_id, bucket_name, prefix=None):
    """Returns the largest week number from the filenames in the google bucket.

    Args:
        project_id (str): id of the google project
        bucket_name (str): name of the bucket
        prefix (str, optional): prefix of the files in the bucket. Defaults to None.

    Returns:
        int: The largest week number found.
    """
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    
    max_number = -1
    pattern = r'^(\d+)\.pkl$'  # Matches {number}.pkl

    for blob in blobs:
        filename = os.path.basename(blob.name)
        match = re.match(pattern, filename)
        if match:
            number = int(match.group(1))  # The number is the first group in the match
            max_number = max(max_number, number)
    
    if max_number == -1:
        print(f"No files found with the format '{{number}}.pkl' in {bucket_name}/{prefix}")
        return -1

    return max_number

def get_google_sheets_id(link):
    """Gets the google sheets id from a google sheets link

    Args:
        link (string): link to google sheets

    Returns:
        string: google sheets id
    """
    parts = link.split("/")
    
    # Checking if URL is a Google Sheets URL
    if "docs.google.com" in parts and "spreadsheets" in parts:
        try:
            # Getting the index of 'd' which is just before the id part
            index = parts.index('d')

            # Returning the next part which is the id
            return parts[index + 1]
        except ValueError:
            print("Invalid Google Sheets URL")
            return None
    else:
        print("URL is not a Google Sheets URL")
        return None

def filter_last_row_by_email(sheet_values):
    """Given a list of lists representing google sheets values,
    filter the list to only include the last row for each email address.

    Args:
        sheet_values (list): list of lists representing google sheets values,
        each list being a row in the google sheet

    Returns:
        list: list of lists with only the last row for each email address
    """
    email_dict = {}
    result = []

    for row in sheet_values:
        email = row[0]  # Assuming the email address is at the first index
        email_dict[email] = row

    for email in email_dict:
        result.append(email_dict[email])

    return result

def nearest_future_monday(date_string):
    # Convert the input string to a datetime object
    date_obj = datetime.strptime(date_string, '%Y-%m-%d')
    
    # Find out what day of the week the date falls on
    day_of_week = date_obj.weekday()

    if day_of_week == 0:
        return date_obj
    return date_obj + timedelta(days=(7 - day_of_week))


def list_blobs_with_prefix(bucket_name, prefix, delimiter=None):
    """Lists all the blobs in the bucket that begin with the prefix.

    This can be used to list all blobs in a "folder", e.g. "public/".

    The delimiter argument can be used to restrict the results to only the
    "files" in the given "folder". Without the delimiter, the entire tree under
    the prefix is returned. For example, given these blobs:

        a/1.txt
        a/b/2.txt

    If you specify prefix ='a/', without a delimiter, you'll get back:

        a/1.txt
        a/b/2.txt

    However, if you specify prefix='a/' and delimiter='/', you'll get back
    only the file directly under 'a/':

        a/1.txt

    As part of the response, you'll also get back a blobs.prefixes entity
    that lists the "subfolders" under `a/`:

        a/b/
    """

    storage_client = storage.Client()

    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)

    # Note: The call returns a response only when the iterator is consumed.
    print("Blobs:")
    for blob in blobs:
        print(blob.name)

if __name__ == '__main__':
    config = config_read.read_config(paths.CONFIG_DIR / "config.json")
    prefix = f"{config['class']}-{config['semester']}"
    
    # get last state
    latest_week = get_latest_week(config["project_id"], config["bucket_name"], prefix)
    if latest_week > -1:
        last_state = deserialize(config.get("project_id"), config["bucket_name"], latest_week, config["weeks_skipped"], prefix)
    else:
        last_state = None
    
    last_state.print_algo_outputs()

def deserialize(week_num, weeks_skipped=1, folder_path=None):
    """
    Deserializes objects from the specified local folder. 
    Also deserializes objects from previous weeks so that prev_state is populated.

    Args:
        folder_path (str | Path | None): Path to the folder containing the serialized objects.
        week_num (int): Week number to start deserialization from.
        weeks_skipped (int): Number of weeks to skip when deserializing.

    Returns:
        state: The deserialized state object for week_num.
    """
    print("deserializing pickle file...")

    target_path = Path(folder_path) if folder_path else paths.PICKLE_DIR
    if not target_path.exists():
        legacy_root = Path("outputs") / "pickles"
        try:
            relative_suffix = target_path.relative_to(paths.PICKLE_DIR)
            legacy_candidate = legacy_root / relative_suffix
        except ValueError:
            legacy_candidate = legacy_root

        if legacy_candidate.exists():
            target_path = legacy_candidate
        else:
            target_path.mkdir(parents=True, exist_ok=True)

    total_states = max(week_num - weeks_skipped, 0)
    if total_states == 0:
        return None

    deserialized_objects = [None] * total_states

    for pickle_path in sorted(target_path.glob("*.pkl")):
        name = pickle_path.stem
        if not name.isdigit():
            continue

        current_week_num = int(name)
        if weeks_skipped < current_week_num <= week_num:
            with pickle_path.open('rb') as file:
                data = _load_compat_pickle(file)
            deserialized_objects[current_week_num - weeks_skipped - 1] = data

    # Link states
    for i in range(len(deserialized_objects) - 1):
        if deserialized_objects[i+1] is not None:
            deserialized_objects[i+1].prev_state = deserialized_objects[i]

    # Return the state object for the current week
    print("returning deserialized state...")
    return deserialized_objects[-1]


# -------- deprecated ------- #
def remote_deserialize(project_id, bucket_name, week_num, weeks_skipped, prefix=None):
    """
    deprecated because shm didn't want to set up google cloud storage
    Deserializes objects from the specified Google Cloud Storage folder
    Also deserializes objects form previous weeks so that prev_state is populated.

    Args:
        folder (str): Path to the folder containing the serialized objects.
        week_num (int): Week number to start deserialization from.

    Returns:
        state: The deserialized state object for week_num.
    """
    # Check each file and only deserialize all states below or equal to week_num
    deserialized_objects = [None] * (week_num - weeks_skipped)

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    target_filename = '{}/{}.pkl'.format(prefix, week_num)
    blobs = bucket.list_blobs(prefix=prefix)  # List all blobs with the given prefix

    for blob in blobs:
        print(blob.name)
        if blob.name.endswith('.pkl'):
            no_prefix_blob_name = os.path.basename(blob.name)
            name = no_prefix_blob_name.split('.')[0]
            if (not name.isdigit()):
                continue
            current_week_num = int(name)
            pickled_data = blob.download_as_bytes()
            data = pickle.loads(pickled_data)
            deserialized_objects[current_week_num - weeks_skipped - 1] = data
    
    # Link states
    for i in range(len(deserialized_objects) - 1):
        deserialized_objects[i+1].prev_state = deserialized_objects[i]
    
    # Return the state object for the current week
    return deserialized_objects[-1]

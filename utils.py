from __future__ import print_function
import os.path
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import collections
import numpy as np
import pickle
from bidict import bidict
from datetime import datetime, timedelta
import State

# Set to readonly
SCOPE = ['https://www.googleapis.com/auth/spreadsheets.readonly',
         'https://www.googleapis.com/auth/calendar']

def get_sheet_values(spread_sheet_id, range):
    """ Creates credentials and reads from a google sheet.

    Args:
        spread_sheet_id (string): ID of the google sheet to read from.
        range (string): google sheet range string to read from

    Returns:
       list: Returns a list of lists, where each list is a row in the sheet. The first row is the header row.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPE)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPE)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spread_sheet_id,
                                    range=range).execute()

        # Get values from sheet
        values = result.get('values', [])
        if not values:
            print('No data found.')
            return None
        return values
    except HttpError as err:
        print(err)
        return None

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
        np_array: a (total_weeks, days, times) np array of the demand for OH
    """
    values = get_sheet_values(sheet_id, range)
    if not values:
        raise Exception('No OH demand information found.')
    
    output = np.full((total_weeks, 5, 12), -1)
    weekday_mapping = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}
    hours_mapping = {"9:00 AM": 0, "10:00 AM": 1, "11:00 AM": 2, "12:00 PM": 3, "1:00 PM": 4, "2:00 PM": 5, "3:00 PM": 6, "4:00 PM": 7, "5:00 PM": 8, "6:00 PM": 9, "7:00 PM": 10, "8:00 PM": 11}
    next_hour_validation = {"9:00 AM": "10:00 AM", "10:00 AM": "11:00 AM", "11:00 AM": "12:00 PM", "12:00 PM": "1:00 PM", "1:00 PM": "2:00 PM", "2:00 PM": "3:00 PM", "3:00 PM": "4:00 PM", "4:00 PM": "5:00 PM", "5:00 PM": "6:00 PM", "6:00 PM": "7:00 PM", "7:00 PM": "8:00 PM", "8:00 PM": "9:00 PM"}


    for row in values:
        if row[0]: # Ensure merged cells (empty cells after merged value) use the correct week
            weeks_str = row[0]
            valid_week = re.compile(r"([0-9]+)||([0-9]+, )+")
            # TODO: Add validation for unique weeks, no duplicate weeks
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
                raise ValueError(f"Error: {week_index} is not a valid week. Must be between 1 and total_weeks ({total_weeks}) (inclusive).")
            if output[week_index - 1][day_index][hour_index] != -1:
                raise ValueError(f"Error: {week_index} {day} {starting_hour} is already filled. Is there a duplicate week/day/hour?")
            output[week_index - 1][day_index][hour_index] = int(num_staff)

    if np.any(output == -1):
        raise ValueError("Invalid array. Some values were not filled. Ensure that there is an entry in the oh demand spreadsheet has for every week from 1 to total weeks, for each day, and for all hours 9:00 AM to 9:00 PM, and that there are no duplicate weeks/days/hours.")
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
    
    rows = values[1:]
    for row in rows:
        row[State.course_staff.total_weekly_hours_index] = int(row[State.course_staff.total_weekly_hours_index])
        row[State.course_staff.semesters_on_staff_index] = int(row[State.course_staff.semesters_on_staff_index])
        row[State.course_staff.semesters_as_ai_index] = int(row[State.course_staff.semesters_as_ai_index])
        row[State.course_staff.weekly_oh_hours_index] = int(row[State.course_staff.weekly_oh_hours_index])
        row[State.course_staff.preferred_contiguous_hours_index] = int(row[State.course_staff.preferred_contiguous_hours_index])

        for i in State.course_staff.availabilities_indices:
            preference = extract_preference(row[i])
            row[i] = preference
    return rows




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

def extract_preference(str):
    """
    Takes in a string representing preference for a time slot in the
    availabilities spreadsheet, which can take the forms of:
    "1 - I'd love this time", "2", "3 - I'd be ok with this", "4", or "5 - Not Possible.", and
    extracts just the first number as an int

    Args:
        str (string): string representing preference for a time slot in the availabilities spreadsheet 

    Raises:
        ValueError: If the first character of the input string is not a number.

    Returns:
        num (int): The first number in the input string.
    """
    if not str:
        raise ValueError('There was no preference input for this time slot.')
    
    # Extract the first character from the string
    num_str = str[0]
    
    # Check if the character is a digit
    if not num_str.isdigit():
        raise ValueError('The first character of the input string must be a digit.')
    
    # Convert the string to an integer
    num = int(num_str)

    return num

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

def deserialize(folder, week_num, weeks_skipped):
    """
    Deserializes objects from the specified folder for the given week. 
    Also deserializes objects form previous weeks so that prev_state is populated.

    Args:
        folder (str): Path to the folder containing the serialized objects.
        week_num (int): Week number to start deserialization from.

    Returns:
        state: The deserialized state object for week_num.
    """
    # Check each file and only deserialize all states below or equal to week_num
    deserialized_objects = [None] * (week_num - weeks_skipped)
    for filename in os.listdir(folder):
        if filename.endswith('.pkl'):
            file_path = os.path.join(folder, filename)
            current_week_num = int(filename.split('.')[0])
            if current_week_num <= week_num:
                with open(file_path, 'rb') as f:
                    obj = pickle.load(f)
                    deserialized_objects[current_week_num - weeks_skipped - 1] = obj
    
    # Link states
    for i in range(len(deserialized_objects) - 1):
        deserialized_objects[i+1].prev_state = deserialized_objects[i]
    
    print(deserialized_objects)
    
    # Return the state object for the current week
    return deserialized_objects[-1]

def get_latest_week(folder_path):
    """Returns the largest week number from the filenames in the specified folder.

    Args:
        folder_path (str): Path to the folder containing the pickle objects.

    Returns:
        int: The largest week number found.
    """
    largest_week_num = -1
    for filename in os.listdir(folder_path):
        if filename.endswith('.pkl'):
            try:
                week_num = int(filename.split('.')[0])
                largest_week_num = max(largest_week_num, week_num)
            except ValueError:
                pass  # Ignore files with non-numeric week numbers
    return largest_week_num

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

def main():
    import config_read
    config = config_read.read_config("config.json")

    demand_id = get_google_sheets_id(config["demand_link"])
    demand = get_demand(demand_id, config_read.DEMAND_RANGE, 15)
    print(demand.take([list(range(10,15))], axis=0))

if __name__ == '__main__':
    main()
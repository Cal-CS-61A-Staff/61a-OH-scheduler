from __future__ import print_function
import copy
import os.path
import collections
import pprint
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import utils
import numpy as np
import pandas as pd
import pickle


def get_availabilities_dataframe(availabilities_id, range, mappings):
    """
    Creates a dataframe from the availabilities spreadsheet, where each row
    represents a student and columns are
    [email, [5x12 matrix of availabilities (scores from 1-5 for preference)]]


    Args:
        availabilities_id (string): ID of the google sheet to read from. 
        range (string): google sheets range string to read from
        mappings (dict): dictionary of [email, index] mappings for the
        dataframe. Must always have the same length as the dataframe's number of
        rows

    Returns:
        dataframe (pandas.DataFrame): [email, [5x12 matrix of availabilities (scores from 1-5 for preference)]]
    """
    # Create sheet object and get all values
    values = utils.get_sheet_values(availabilities_id, range)
    if not values:
        raise Exception('No staff availabilities data found.')
    
    # Split values and header row
    header_row = values[0]
    values = values[1:]
    print("header", header_row)
    print(values)


#     pattern = re.compile(r"(\w+) \[(\d+:\d+.*- \d+:\d+.*)\]")

#     # start from 3 as 0 is email address, 1 is appointed hours, 2 is preferred hours
#     for i in range(3, len(header_row)): 
#         match = pattern.fullmatch(header_row[i])
#         day = match.group(1)
#         time = match.group(2)
#         temp_times_dict = {'1': [], '2': [], '3': [], '4': [], '5': []}
        
#         availabilities_dict[day][time] = temp_times_dict

#     # Add each value
#     for i in range(1, len(values)):
#         row = values[i]
#         email = row[0]
#         for j in range(3, len(values[0])):
#             match = pattern.fullmatch(header_row[j])
#             day = match.group(1)
#             time = match.group(2)
#             score = row[j][0]
#             availabilities_dict[day][time][score].append(email)
#     return availabilities_dict

# def get_staff_appointed_and_preferred_hours():
#     """ Returns a dictionary with all staff appointed and preferred contiguous hours

#     Returns:
#         dictionary: format below
#         {"appointed": {"email1" : 3, "email2" : 2, ...},
#          "preferred": {"email1" : 5, "email2" : 4, ...}}
#     """
#     values = utils.get_sheet_values(AVAILABILITIES_SPREADSHEET_ID, APPOINTED_PREFERRED_HOURS_RANGE, SCOPES)
#     if not values:
#         print('No data found.')
#         return
#     print(values)
    
#     # Create dictionary without values
#     preferred_appointed_dict = {'appointed': {}, 'preferred': {}}
#     # Add each value
#     print(values)
#     for i in range(1, len(values)):
#         preferred_appointed_dict['appointed'][values[i][0]] = values[i][1]
#         preferred_appointed_dict['preferred'][values[i][0]] = values[i][2]
#     print(preferred_appointed_dict)
#     return preferred_appointed_dict

def get_max_and_preferred_hours_array(mappings, config_multiplier):
    """
    Returns 2 arrays of size n, for the max number of hours for each staff
    member and their preferred number of contiguous hours.

    Args:
        mappings (dict): dictionary with n items, n = # of current staff. Maps
        indices to email. config_multiplier (int): multiplier from config_read.

    Returns:
        np.array of length n, n = len(mappings). Where index i corresponds to
        the appointed hours of the ith staff (using mapping)
         np.array of length n, n = len(mappings). Where index i corresponds to
         the preferred contiguous hours of the ith staff (using mapping)
    """
    values_dict = get_staff_appointed_and_preferred_hours()

    appointed_hours = np.zeros(len(mappings.keys()))
    for key in mappings:
        appointed_hours[key] = values_dict['appointed'][mappings[key]] * config_multiplier

    preferred_hours = np.zeros(len(mappings.keys()))
    for key in mappings:
        preferred_hours[key] = values_dict['preferred'][mappings[key]]

    return appointed_hours, preferred_hours

def get_availabilities_by_email(all_data):
    """Get availabilities dictionary mapping emails to timeslots and preferences

    Args:
        all_data (_type_): Dictionary of all data from the get_all_data() function

    Returns:
        dict: Availabilities dictionary mapping emails to timeslots and preferences
    """
    data = collections.defaultdict(lambda: collections.defaultdict(dict))

    for day in all_data.keys():      
        for time in all_data[day].keys():
            for pref in all_data[day][time].keys():
                for email in all_data[day][time][pref]:
                    data[email][day][time] = pref

    return data

def get_remaining_hours(previous_hours, new_hours_worked_since, old_mapping, new_mapping, appointed_hours, weeks_left):
    remaining_hours = np.zeros(len(new_mapping.keys()))
    for key in new_mapping:
        value = new_mapping[key]
        previous_key = [i for i in old_mapping if old_mapping[i] == value]
        if not previous_key:
            remaining_hours[key] = appointed_hours[key] * weeks_left
            continue
        previous_key = previous_key[0]
        print(previous_hours, previous_key, new_hours_worked_since, key)
        remaining_hours[key] = previous_hours[previous_key] - new_hours_worked_since[key]
    return remaining_hours

def get_availabilities_array_and_mapping(avail_emails_dict):
    """Get numpy array for availabilities and mapping of index in that array to emails

    Args:
        avail_emails_dict (_type_): Dictionary mapping email to availabilities from get_availabilities_from emails()

    Returns:
        numpy arr: Availabilities array
        dict: Mapping
    """
    mapping = collections.defaultdict(int)
    avail_arr = []
    for i,email in enumerate(avail_emails_dict.keys()):
        avail_arr.append([])
        mapping[email] = i
        for day in avail_emails_dict[email].keys():
            avail_arr[-1].append([])
            for time in avail_emails_dict[email][day].keys():
                avail_arr[-1][-1].append(avail_emails_dict[email][day][time])
    
    return avail_arr, mapping
    

def get_changed_availabilities(cur_avail_dict, current_mapping):
    """Process changed staff availabilities

    Args:
        cur_avail (npy): Numpy array of current availabilities

    Returns:
        changed_ind (list): Indices of changed staff in current availabilities array
        changed_arr (npy): Changed staff's previous availabilities 
        (e.g. Staff at index 5 in changed_ind will have previous availabilities at changed_arr index 5)
    """
    prev_mapping = load_mapping()
    prev_avail_dict = load_avail_dict()
    prev_avail_arr = load_avail_arr()
    changed_ind = []
    changed_arr = []
    new_ind = []
    new_arr = []
    zeros_arr = np.zeros((5,12))
    for staff_member in cur_avail_dict.keys():
        if prev_avail_dict.get(staff_member, None) is None:
            new_ind.append(current_mapping[staff_member])
            new_arr.append(zeros_arr)
        else:
            entries_not_equal = not (cur_avail_dict[staff_member] == prev_avail_dict[staff_member])
            if entries_not_equal:
                changed_ind.append(current_mapping[staff_member])
                ind = prev_mapping[staff_member]
                changed_arr.append(prev_avail_arr[ind])
    return changed_ind, changed_arr, new_ind, new_arr

def save_mapping(data):
    # Store data (serialize) 
    #TODO: Grace will do this
    pickle.dump(data, open("mapping.p", "wb"))

def load_mapping():
    # Load data (deserialize):
    #TODO: Grace will give input
    data = pickle.load(open("mapping.p", "rb"))
    return data

def save_avail_arr(data):
    #TODO: Grace will do this
    np.save("avail_data", data)

def load_avail_arr():
    #TODO: Grace will give input
    load_arr = np.load("avail_data.npy", allow_pickle=True)
    return load_arr

def save_avail_dict(data):
    #TODO: Grace will do this
    pickle.dump(data, open("avail_dict.p", "wb"))

def load_avail_dict():
    #TODO: Grace will give input
    data = pickle.load(open("avail_dict.p", "rb"))
    return data

# needs to be able to update
# tensor dimension:
# row: each day
# column: each time slot
# width: # of staff. 

def main():
    id = "1N6bDWK4yZT_BCLjpnDjJ7GOhJwL_romFrtM-SAlm390"
    range = "Form Responses 1!B1:BL"
    get_availabilities_dataframe(id, range, {"cyrushung822@berkeley.edu": 0, "cyrus.hung123@gmail.com": 1})

if __name__ == '__main__':
    main()
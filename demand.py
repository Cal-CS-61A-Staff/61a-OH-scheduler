from __future__ import print_function

import os.path
import collections
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import re
import utils

# The ID and range of a sample spreadsheet.
DEMAND_SPREADSHEET_ID = '19q2u8MTFQbl7J1fm8L97JDjMKDqZJabyB7K5bk76cDU'
DEMAND_RANGE_NAME = 'Demand!A2:E'


def get_demand(sheet_id, range):
    """
    Gets the demand for OH from the spreadsheet. The result will be an np array of shape (weeks, days, times), 
    which should be (weeks, 5, 12) where each value is the number of OH needed for that time slot. 

    Args:
        sheet_id (string): google sheet ID to read from
        range (_type_): range to read from

    Raises:
        Exception: No OH demand was found for this link/range

    Returns:
        np_array: a (weeks, days, times) np array of the demand for OH
    """
    values = utils.get_sheet_values(sheet_id, range)
    if not values:
        raise Exception('No OH demand information found.')

    readable_data = collections.defaultdict(dict)
    for row in values:
        if row[0]: # Ensure merged cells (empty cells after merged value) use the correct week
            weeks_str = row[0]
            valid_week = re.compile(r"([0-9]+)||([0-9]+, )+")
            # TODO: Add validation for unique weeks, no duplicate weeks
            if not valid_week.match(weeks_str):
                print(f"Error: {weeks_str} is not in the correct format (e.g. 2, 3, 4).")
                return

            weeks = [int(week) for week in weeks_str.split(", ")]
            temp_week_dict = collections.defaultdict(list)
        
        if row[1]: # Ensure merged cells (empty cells after merged value) use the correct day
            day = row[1]
            valid_day = re.compile(r"(Monday)||(Tuesday)||(Wednesday)||(Thursday)||(Friday)")
            if not valid_day.match(day):
                print(f"Error: {day} is not in the correct format (e.g. Monday, Tuesday).")
                return

        num_staff = row[4]
        valid_num_staff = re.compile(r"[0-9]+")
        if not valid_num_staff.match(num_staff):
            print(f"Error: {num_staff} is not in the correct format (int).")
            return
        temp_week_dict[day].append(int(num_staff))

        if not row[0]:
            for week in weeks:
                readable_data[week] = dict(temp_week_dict)
    # Sort ascending by week
    readable_data = {i: readable_data[i] for i in sorted(dict(readable_data).keys())} 
            
    algo_data = []
    for week in readable_data.values():
        algo_data.append([])
        
        for day in week.values():
            algo_data[-1].append(day)
            
    return algo_data

if __name__ == '__main__':
    get_demand()
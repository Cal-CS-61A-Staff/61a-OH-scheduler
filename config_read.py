import json
import utils
import State

def read_config(config):
    """Reads the configuration file and creates a dictionary

    Args:
        config (string): path to config json file

    Returns:
        dictionary: 
        {
            "demand_link" (str): link to spreadsheet with OH demand.
            "availabilities_link" (str): link to spreadsheet with OH availabilities.
            "project_id" (str): project id containing the cloud storage bucket
            "bucket_name" (str): bucket name of the cloud storage bucket
            "class" (str): class this output is for (e.g. cs61a)
            "semester" (str): current semester (e.g. sp23)
            "weeks" (int): number of weeks in a semester
            "weekly_hour_multiplier" (int): multiplier for the max amount of hours per person, default: 2
            "start_date (str): Starting date of when to run this algorithm in YYYY-MM-DD format
            "weeks_skipped" (int): number of weeks (since the start of instruction,
            included in total weeks) that have passed by the starting date.
            "calendar_event_name" (str): name of the calendar event that will be created
            "calendar_event_location" (str): name of the calendar event location that will be created
            "calendar_event_description" (str): description of the calendar event that will be created
        }
    """
    f = open(config)
    data = json.load(f)
    f.close()

    if "weekly_hour_multiplier" not in data:
        data["weekly_hour_multiplier"] = 2
    
    data["weeks"] = int(data["weeks"])
    data["weekly_hour_multiplier"] = int(data["weekly_hour_multiplier"])
    data["weeks_skipped"] = int(data["weeks_skipped"])

    return data

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
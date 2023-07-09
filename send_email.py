import datetime
import numpy as np
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dateutil.relativedelta import relativedelta, MO
import utils

import os


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def send_invites(email, np_array, start_date, calendar_name, calendar_location, calendar_description):
    # Ensure start_date is a Monday
    if start_date.weekday() != 0:
        start_date = start_date + relativedelta(weekday=MO)

    # creds = service_account.Credentials.from_service_account_file(
    #     "credentials.json", scopes=SCOPES
    # )

    # service = build('calendar', 'v3', credentials=creds)

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'local_oauth_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('calendar', 'v3', credentials=creds)


    for i in range(np_array.shape[0]):
        j = 0
        while j < np_array.shape[1]:
            if np_array[i, j] == 1:
                # Calculate date and time for the event
                event_date = start_date + datetime.timedelta(days=i)
                start_time = datetime.time(9+j, 0)
                while j < np_array.shape[1] and np_array[i, j] == 1:
                    j += 1
                end_time = datetime.time(9+j, 0)

                # Create the event
                event = {
                    'summary': calendar_name,
                    'location': calendar_location,
                    'description': calendar_description,
                    'start': {
                        'dateTime': datetime.datetime.combine(event_date, start_time).isoformat(),
                        'timeZone': 'America/Los_Angeles',
                    },
                    'end': {
                        'dateTime': datetime.datetime.combine(event_date, end_time).isoformat(),
                        'timeZone': 'America/Los_Angeles',
                    },
                    'attendees': [
                        {'email': email},
                    ],
                    'reminders': {
                        'useDefault': True,
                    },
                }

                # Call the Calendar API
                event = service.events().insert(calendarId='primary', sendNotifications=True, body=event).execute()
            j += 1
            

if __name__ == "__main__":
    timeslots = np.zeros((5, 12))  # Random example array
    timeslots[1][1] = 1
    timeslots[1][2] = 1

    monday_date = utils.nearest_future_monday('2023-07-17')
    print(timeslots)
    send_invites('main.share.us@gmail.com', timeslots, monday_date, "OH time", "warren", "damn I love this OH")
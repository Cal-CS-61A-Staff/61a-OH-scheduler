import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta

from . import paths

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']


def authenticate():
    """Handles authentication and returns a Google Calendar service object."""
    creds = None
    paths.ensure_directories()
    oauth_path = paths.CREDS_DIR / 'oauth_credentials.json'
    token_path = paths.CREDS_DIR / 'token.json'

    # Check if oauth_credentials.json exists
    if not oauth_path.exists():
        raise FileNotFoundError(
            "ERROR: oauth_credentials.json not found in the credentials/ folder. "
            "Go to the Google Cloud Console for the CS61A SPA account "
            "(https://console.cloud.google.com/apis/credentials?project=cs-61a-website) "
            "and under APIs & Services > Credentials, download the "
            "oh_scheduler_oauth OAuth 2.0 Client ID, and save it as credentials/oauth_credentials.json."
        )

    # The file token.json stores the user's access and refresh tokens and is
    # created automatically when the authorization flow completes for the first time.
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
             # Ask for user approval
            approval = input("\n\033[1mLooking for OAuth creds... If they are not found, a browser window should open prompting you to log into the CS61A SPA account. Press any key to continue.\033[0m").strip().lower()
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(oauth_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with token_path.open('w') as token:
            token.write(creds.to_json())

    # Build and return the Calendar API service object
    service = build('calendar', 'v3', credentials=creds)
    return service


def create_event(service, calendar_id, summary, location, description, start_time, end_time, attendees, reminders):
    """
    Creates an event in a specified calendar and sends invite emails to attendees.
    
    Parameters:
    ----------
    service : googleapiclient.discovery.Resource
        output of running authenticate()
    calendar_id : str
        ID of the calendar where the event will be created.
    summary : str
        Title of the event.
    location : str
        Location of the event.
    description : str
        Description of the event.
    start_time : str
        Start time of the event in RFC3339 format (e.g., '2024-10-01T09:00:00-07:00').
    end_time : str
        End time of the event in RFC3339 format.
    attendees : list of str
        List of attendee email addresses.
    reminders : dict
        reminder settings
    """
    
    
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Los_Angeles',
        },
        'attendees': [{'email': email} for email in attendees],
        'reminders': reminders if reminders is not None else {'useDefault': True}
    }

    try:
        event_result = service.events().insert(
            calendarId=calendar_id, 
            body=event,
            sendUpdates='all'  # Send email invitations to attendees
        ).execute()
        
        print(f"Event created at {start_time}: {event_result.get('htmlLink')}")
    except HttpError as error:
        print(f"An error occurred: {error}")



def main():
    """test out the calendar functionality"""
    print("The first time you run this program, it will ask you to log in. Make sure to log into the CS61A SPA account!")
    try:
        # Authenticate and get the service object
        service = authenticate()

        # Step 1: Ask the user if they want to test the calendar functionality
        test_calendar = input("Do you want to run a test of the calendar event functionality? (y/n): ").lower()

        if test_calendar == 'y':
            # get tomorrow's date (9-10AM)
            tomorrow_9 = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%S-07:00')
            tomorrow_10 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%S-07:00')


            # Step 2: Ask for an email address to invite to the test event
            email_address = input("Enter an email address you'd like to invite to the test event (e.g. your personal email): ")

            # Step 3: Create a test event
            config = {"calendar_id": "c_dd1b34e8fe66665adaa898825ba2ce784febefadbcd53c4a45d369c3628147b1@group.calendar.google.com"}  # Replace with your calendar ID

            # Define test event details
            summary = "Test Event"
            location = "123 Main St, Anytown, USA"
            description = "This is a test event created using OAuth."
            start_time = tomorrow_9 
            end_time = tomorrow_10
            attendees = [email_address]
            reminders = {
                'useDefault': False,
                'overrides': [
                    #{'method': 'email', 'minutes': 24 * 60},
                ],
            }

            # Call the create_event function
            create_event(service, config["calendar_id"], summary, location, description, start_time, end_time, attendees, reminders)

    except FileNotFoundError as e:
        print(e)
    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == '__main__':
    main()

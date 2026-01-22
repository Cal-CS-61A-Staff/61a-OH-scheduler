import logging
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import paths

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/forms.body", 
    "https://www.googleapis.com/auth/drive",
]

# Days we support when building schedules from the CSV export.
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


logger = logging.getLogger(__name__)


def _get_week_dates(start_date: datetime) -> dict[str, datetime]:
    """Return a mapping from weekday names to dates for the given week."""
    if not isinstance(start_date, datetime):
        raise TypeError("start_date must be a datetime.datetime instance")

    monday = start_date - timedelta(days=start_date.weekday())
    return {
        day: monday + timedelta(days=offset)
        for offset, day in enumerate(DAYS)
    }


def authenticate():
    """Handles authentication and returns a Google Calendar service object."""
    creds = None
    paths.ensure_directories()
    oauth_path = paths.CREDS_DIR / 'oauth_credentials.json'
    token_path = paths.CREDS_DIR / 'token.json'

    # Check if oauth_credentials.json exists
    if not oauth_path.exists():
        logger.error("OAuth credentials file missing at %s.", oauth_path)
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
        logger.debug("Loading cached OAuth token from %s.", token_path)
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        logger.info("OAuth credentials invalid or missing; starting refresh/flow.")
        if creds and creds.expired and creds.refresh_token:
             # Ask for user approval
            approval = input("\n\033[1mLooking for OAuth creds... If they are not found, a browser window should open prompting you to log into the CS61A SPA account. Press any key to continue.\033[0m").strip().lower()
            logger.debug("Refreshing OAuth token with stored refresh token.")
            creds.refresh(Request())
        else:
            logger.info("Running OAuth browser flow using client secrets at %s.", oauth_path)
            flow = InstalledAppFlow.from_client_secrets_file(str(oauth_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        logger.debug("Writing refreshed OAuth token to %s.", token_path)
        with token_path.open('w') as token:
            token.write(creds.to_json())

    # Build and return the Calendar API service object
    logger.info("Creating Google Calendar service client.")
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
        logger.info(
            "Creating calendar event '%s' (%s – %s) for %d attendee(s).",
            summary,
            start_time,
            end_time,
            len(attendees),
        )
        event_result = service.events().insert(
            calendarId=calendar_id, 
            body=event,
            sendUpdates='all'  # Send email invitations to attendees
        ).execute()
        
        print(f"Event created at {start_time}: {event_result.get('htmlLink')}")
    except HttpError as error:
        logger.error(
            "Failed to create event '%s' (%s – %s): %s",
            summary,
            start_time,
            end_time,
            error,
        )
        print(f"An error occurred: {error}")


def build_event_payloads(assignments, config, demand_metadata):
    """Prepare Google Calendar event payloads from assignment data."""
    timezone = ZoneInfo('America/Los_Angeles')
    events = []
    skipped_slots = []

    for assignment in assignments:
        attendees = [email for email in assignment["attendees"] if email]
        if not attendees:
            skipped_slots.append((assignment.get("day"), assignment.get("hour_key")))
            continue

        start_dt = datetime.strptime(assignment["start_time"], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone)
        end_dt = datetime.strptime(assignment["end_time"], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone)

        slot_meta = demand_metadata.get((assignment.get("day"), assignment.get("hour_key"))) if demand_metadata else None
        summary = config.get('calendar_event_name', 'Office Hours')
        location = (slot_meta.get('location') if slot_meta else None) or config.get('calendar_event_location', '')
        description_source = (slot_meta.get('description') if slot_meta else None) or config.get('calendar_event_description', '')
        total_staff_value = (slot_meta.get('total_staff') if slot_meta else None) or config.get('calendar_event_total_staff', '')
        comments_value = (slot_meta.get('comments') if slot_meta else None) or config.get('calendar_event_comments', '')

        description_parts = []
        if description_source:
            description_parts.append(description_source)
        if total_staff_value:
            description_parts.append(f"Total staff: {total_staff_value}")
        if comments_value:
            description_parts.append(f"Comments: {comments_value}")

        description = "\n".join(description_parts)

        reminders = {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        }

        event_payload = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_dt.isoformat(timespec='seconds'),
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': end_dt.isoformat(timespec='seconds'),
                'timeZone': 'America/Los_Angeles',
            },
            'attendees': [{'email': email} for email in attendees],
            'reminders': reminders,
        }

        events.append(event_payload)

    logger.info(
        "Prepared %d event payload(s); skipped %d slot(s) with no attendees.",
        len(events),
        len(skipped_slots),
    )
    return events, skipped_slots


def preview_calendar_events(events):
    """Print a human-readable summary of the calendar events to be created."""
    print(f"\nPreview of calendar events to be created ({len(events)} total):\n")

    for idx, event in enumerate(events, start=1):
        start_dt = datetime.fromisoformat(event['start']['dateTime']).astimezone(ZoneInfo('America/Los_Angeles'))
        end_dt = datetime.fromisoformat(event['end']['dateTime']).astimezone(ZoneInfo('America/Los_Angeles'))

        start_str = start_dt.strftime("%A, %B %d, %Y at %I:%M %p")
        end_str = end_dt.strftime("%I:%M %p")

        attendees = [att['email'] for att in event['attendees']]
        attendee_count = len(attendees)
        if attendee_count == 0:
            attendees_display = "None"
        else:
            attendees_display = ", ".join(attendees[:5])
            if attendee_count > 5:
                attendees_display += f", +{attendee_count - 5} more"

        description_lines = [line for line in event['description'].splitlines() if line.strip()]

        print(f"{idx}. {event['summary']}")
        print(f"   When: {start_str} – {end_str} (America/Los_Angeles)")
        if event['location']:
            print(f"   Where: {event['location']}")
        if description_lines:
            print("   Description:")
            for line in description_lines:
                print(f"      {line}")
        else:
            print("   Description: (empty)")

        print(f"   Attendees ({attendee_count}): {attendees_display}")

        reminders = event.get('reminders', {})
        overrides = reminders.get('overrides') or []
        if overrides:
            reminder_parts = []
            for override in overrides:
                method = override.get('method', 'unknown')
                minutes = override.get('minutes')
                if minutes is None:
                    reminder_parts.append(method)
                    continue
                hours, mins = divmod(minutes, 60)
                timing_parts = []
                if hours:
                    timing_parts.append(f"{hours}h")
                if mins:
                    timing_parts.append(f"{mins}m")
                if not timing_parts:
                    timing_parts.append("0m")
                reminder_parts.append(f"{method} {' '.join(timing_parts)} early")
            print("   Reminders: " + ", ".join(reminder_parts))
        else:
            print("   Reminders: none (useDefault=False)")

        print()


def send_assignments_to_calendar(assignments, config, demand_metadata):
    """Authenticate, preview, and send calendar events for the provided assignments."""
    service = authenticate()
    calendar_id = config.get('calendar_id')
    if not calendar_id:
        logger.error("No calendar_id provided in config; aborting event creation.")
        print("Calendar ID missing from config; cannot create events.")
        return

    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
        calendar_name = calendar.get('summary', calendar_id)
        logger.info("Using calendar '%s' (%s).", calendar_name, calendar_id)
        print(f"Calendar Name: {calendar_name}")
    except HttpError as error:
        logger.error("Failed to fetch calendar metadata for %s: %s", calendar_id, error)
        print(f"An error occurred while fetching calendar information: {error}")
        return

    event_payloads, skipped_slots = build_event_payloads(assignments, config, demand_metadata)

    if skipped_slots:
        logger.warning("Skipping %d assignment(s) that lack attendees.", len(skipped_slots))
        print(f"Skipping {len(skipped_slots)} assignment(s) with no attendees.")

    if not event_payloads:
        logger.warning("No event payloads generated; nothing to send.")
        print("No events to create after filtering assignments.")
        return

    preview_calendar_events(event_payloads)

    approval = input("\nCreate the above calendar events? (y/n): ").strip().lower()
    if approval != 'y':
        logger.info("User declined to create calendar events.")
        print("Aborting calendar event creation.")
        return

    creation_errors = False

    for event_payload in event_payloads:
        try:
            create_event(
                service=service,
                calendar_id=calendar_id,
                summary=event_payload['summary'],
                location=event_payload['location'],
                description=event_payload['description'],
                start_time=event_payload['start']['dateTime'],
                end_time=event_payload['end']['dateTime'],
                attendees=[att['email'] for att in event_payload['attendees']],
                reminders=event_payload['reminders'],
            )
            attendees_display = ', '.join(att['email'] for att in event_payload['attendees'])
            print(f"Event created for {event_payload['start']['dateTime']} – {event_payload['end']['dateTime']} with attendees: {attendees_display}\n")
        except HttpError as error:
            logger.error(
                "Error while creating event for %s – %s: %s",
                event_payload['start']['dateTime'],
                event_payload['end']['dateTime'],
                error,
            )
            print(f"An error occurred while creating the event for {event_payload['start']['dateTime']} – {event_payload['end']['dateTime']}: {error}")
            creation_errors = True

    if not creation_errors:
        logger.info("All calendar events created successfully.")
        print("\nAll events created successfully!")
    else:
        logger.warning("At least one calendar event failed to create.")
        print("Some events could not be created due to errors.")



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

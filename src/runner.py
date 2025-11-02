from __future__ import annotations

from googleapiclient.errors import HttpError

import logging
import os
import sys
import numpy as np
from datetime import datetime, tzinfo
from datetime import timedelta
from zoneinfo import ZoneInfo
import csv
from pathlib import Path
# #from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound
import pandas as pd

from src import algorithm
from src import calendar_time
from src import config_read
from src import logging_utils
from src import paths
from src import utils
from src import validation
from src.config_utils import (
    ENV_CLASS_NAME,
    ENV_CONFIG_PATH,
    find_option_by_class,
    load_class_config_options,
    resolve_config_path,
)
from src.state import State


# The range of both spreadsheet. This should not change unless the forms/the demand spreadsheet has been edited.



os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(paths.CREDS_DIR / "credentials.json")
paths.ensure_directories()


def print_header(text: str) -> None:
    print(f"\n\033[1m{text}\033[0m")


def print_subheader(text: str) -> None:
    print(f"  {text}")


def format_hours(hours: float) -> str:
    value = int(hours)
    suffix = "hour" if value == 1 else "hours"
    return f"{value} {suffix}"


def main():
    logging_utils.configure_logging()
    logger = logging.getLogger(__name__)

    print_header("[---- Welcome to the Office Hours Scheduler! ----]")
    class_options = load_class_config_options(logger)
    if not class_options:
        print("No valid class configurations found in the configs/ directory.")
        logger.error("No class configurations available for selection.")
        sys.exit(1)

    selected_option = None
    config_path: Path | None = None
    # Determine the correct config file based on the user's choice (env var or manual selection)
    env_class_name = os.environ.get(ENV_CLASS_NAME)
    if env_class_name:
        selected_option = find_option_by_class(class_options, env_class_name)
        if selected_option:
            config_path = selected_option.path
            print_subheader(
                f"Using class '{selected_option.class_name.upper()}' ({selected_option.path.name})."
            )
            logger.info(
                "Using config for class '%s' from %s (provided via %s).",
                selected_option.class_name,
                selected_option.path,
                ENV_CLASS_NAME,
            )
        else:
            print_subheader(
                f"Class '{env_class_name}' not found. Falling back to manual selection."
            )
            logger.warning(
                "Environment requested class '%s', but no matching config option was found.",
                env_class_name,
            )

    if config_path is None:
        env_config_candidate = os.environ.get(ENV_CONFIG_PATH)
        if env_config_candidate:
            resolved_path = resolve_config_path(env_config_candidate)
            if resolved_path:
                config_path = resolved_path
                print_subheader(f"Using config file '{resolved_path.name}'.")
                logger.info(
                    "Using config at %s (provided via %s).",
                    resolved_path,
                    ENV_CONFIG_PATH,
                )
            else:
                print_subheader(
                    f"Config file '{env_config_candidate}' not found. Falling back to manual selection."
                )
                logger.warning(
                    "Environment requested config path %s, but it could not be resolved.",
                    env_config_candidate,
                )

    if config_path is None:
        print_subheader("Please select the class you're scheduling for:")
        for idx, option in enumerate(class_options, start=1):
            display_name = option.class_name.upper()
            print(f"  [{idx}] {display_name} ({option.path.name})")

        choice = input(f"Enter your choice (1-{len(class_options)}): ").strip()
        try:
            selected_index = int(choice)
        except ValueError:
            print("Invalid choice. Please restart and select a valid option number.")
            logger.warning("Invalid class selection (non-integer): %s", choice)
            return

        if not 1 <= selected_index <= len(class_options):
            print("Invalid choice. Please restart and select a valid option number.")
            logger.warning("Invalid class selection (out of range): %s", choice)
            return

        selected_option = class_options[selected_index - 1]
        config_path = selected_option.path
    elif selected_option is None:
        selected_option = next(
            (option for option in class_options if option.path == config_path),
            None,
        )

    config = config_read.read_config(config_path)
    logger.info("Loaded config from %s", config_path)

    # Which functionality?
    print_header("Select an action")
    print("  [1] Run the OH scheduler (generate CSV file)")
    print("  [2] Send calendar events (CSV file to calendar event invites)")
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == '2':
        week_num = int(input("Enter the week number you'd like to send emails for. \n(e.g., enter 5 for week 5 of the semester): ").strip())
        logger.info("Preparing calendar export for week %s", week_num)
        calendar_events_from_csv(config, week_num)
        sys.exit(0)
    elif choice!= '1':
        print("Invalid choice. Please restart")
        logger.warning("Invalid functionality selection: %s", choice)
        return



    # -- Continue with OH scheduling! -- #

    # Print links and ranges for user approval
    print_header("Current configuration")
    print_subheader(f"Availabilities sheet: {config['availabilities_link']}")
    print_subheader(f"Demand sheet:        {config['demand_link']}")
    print_subheader("Ranges:")
    print_subheader(f"  • AVAILABILITIES_RANGE = {config['AVAILABILITIES_RANGE']}")
    print_subheader(f"  • DEMAND_RANGE         = {config['DEMAND_RANGE']}")

    # Ask for user approval
    approval = input("\n\033[1mDoes everything look correct? (y/n): \033[0m").strip().lower()
    if approval != 'y':
        print("Please edit the relevant config under configs/, then re-run the program.")
        logger.info("User did not approve configuration; exiting.")
        sys.exit(1)

    AVAILABILITIES_RANGE = config["AVAILABILITIES_RANGE"]
    DEMAND_RANGE = config["DEMAND_RANGE"]

    logger.info(f"Using config for class: {config['class']}")
    logger.info(f"Using availabilities link: {config['availabilities_link']}")
    logger.info(f"Using demand link: {config['demand_link']}")
    logger.info(f"Using AVAILABILITIES_RANGE: {AVAILABILITIES_RANGE}")
    logger.info(f"Using DEMAND_RANGE: {DEMAND_RANGE}")

    # Step 3: Fetch and validate availabilities data
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])

    #FYI: this function in utils.py converts the spreadsheet responses into numbers (and handles weird responses, ie when a ta puts "N/A")\/
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validation.validate_availabilities(availabilities)

    # Step 4: Fetch and validate demand data
    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])

    # Step 5: Validate the entire config
    validation.validate_config(config)

    run_scheduler(config, demand, availabilities)


def run_scheduler(config, demand, availabilities):
    logger = logging.getLogger(__name__)

    # Step 5: Prompt user to enter the current week
    while True:
        try:
            week_num = int(input("\nEnter the week number to schedule (e.g., 5 for week 5): ").strip())
            if week_num <= 0:
                raise ValueError

            break
        except ValueError:
            print("Invalid input, please enter a positive integer for the week number.")
            logger.warning("Invalid week number input.")
    #check if we should rerun everything from the beginning
    while True:
        try:
            choice = input("Rerun from the start of the semester? (y/n): ").strip()
            if choice == 'y':
                latest_week = 0
                logger.info("User requested full rerun from week 1.")
                break
            if choice == 'n':
                print_subheader("Running just this week...")
                latest_week = week_num - 1
                logger.info("Running week %s only.", week_num)
                break
        except ValueError:
            print("Invalid input.")
            logger.warning("Invalid rerun selection input.")



    while (latest_week < week_num):
        target_pickle_dir = paths.PICKLE_DIR / config["class"]
        if (latest_week - config["weeks_skipped"]) > 0:
            print_header(f"Week {latest_week + 1}: preparing inputs")
            print_subheader(f"• Loading saved state for week {latest_week}...")
            logger.info("Attempting to load state for week %s", latest_week)
            last_state = utils.deserialize(latest_week, config["weeks_skipped"], folder_path=target_pickle_dir)
        else:
            print_header(f"Week {latest_week + 1}: preparing inputs")
            print_subheader("• No prior state required (starting fresh).")
            last_state = None

        if last_state is None and (latest_week - config["weeks_skipped"]) > 0:
            print_subheader(f"! No state found for week {latest_week}; continuing without history.")
            logger.warning("No saved state for week %s; proceeding without prior context.", latest_week)

        if last_state and last_state.week_num == config["weeks"]:
            print(f"ERROR: The algorithm has already been run for all weeks. The last state was for week {config['weeks']}. Exiting.")
            return
        if latest_week == config['weeks']:
            raise RuntimeError("Allotted # of weeks have already passed. Exiting.")

        target_week = max(latest_week + 1, config["weeks_skipped"] + 1)

        # Create new state object
        state = State(last_state,
                            demand, 
                            availabilities, 
                            config["class"], 
                            config["semester"], 
                            config["weeks"], 
                            config["weekly_hour_multiplier"], 
                            config["weeks_skipped"],
                            current_week=target_week)

        # Run algorithm
        inputs = state.get_algo_inputs()
        print_subheader("• Solving optimisation problem...")
        assignments = algorithm.run_algorithm(inputs)
        # \assignments = np.load("assignments.npy")[:, 0, :, :]

        np.save(paths.NPY_DIR / 'demand.npy', demand)

        state.set_assignments(assignments)
        
        # Validate no one with 0 weekly hours has been assigned any hours
        zero_target_violations = []
        for email, staff_member in state.course_staff_dict.items():
            if staff_member.weekly_oh_hours == 0:
                assigned_hours = staff_member.assigned_hours.sum() if staff_member.assigned_hours is not None else 0
                if assigned_hours > 0:
                    zero_target_violations.append((email, assigned_hours))

        if zero_target_violations:
            message = "Detected assignments for staff with 0 weekly hours: " + ", ".join(
                f"{email} ({hours} hours)" for email, hours in zero_target_violations
            )
            logger.error(message)
            raise RuntimeError(message)

        state.serialize(folder_path=target_pickle_dir) # save the current state as a pickle in appropriate folder
        logger.info("Serialized state for week %s to %s", state.week_num, target_pickle_dir)
        latest_week += 1

    # Create CSV export of that next week's assignments
    print_header("Assignment summary")
    export_dict = {"email": [], "sum_assignments": []}
    for i in range(assignments.shape[0]):
        if assignments[i].sum() != 0:
            email = state.bi_mappings.inverse[i]
            num_hours = assignments[i].sum()
            export_dict['email'].append(email)
            export_dict['sum_assignments'].append(num_hours)
            print_subheader(f"• {email.split('@')[0]:<20} {format_hours(num_hours)}")

    export_df = pd.DataFrame(data=export_dict)
    summary_path = Path(f"outputs/{config['class']}_sum_assignments_week{week_num}.csv")
    export_df.to_csv(summary_path, index=False)
    logger.info("Wrote summary CSV to %s", summary_path)


    # Create a dictionary to store the data for the detailed CSV
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    hours_of_day = [f"{hour}:00" for hour in range(9, 21)]  # 9 AM to 9 PM
    export_dict_weekly = {day: [""] * 12 for day in days_of_week}  # Initialize dictionary for each day

    # Iterate over the days of the week
    for day_index in range(assignments.shape[1]):
        # Iterate over the hours of the day
        for hour_index in range(assignments.shape[2]):
            assigned_staff = []
            # Iterate over each staff member to find those assigned to this time slot
            for staff_index in range(assignments.shape[0]):
                if assignments[staff_index, day_index, hour_index] == 1:  # If the staff member is assigned
                    staff_email = state.bi_mappings.inverse[staff_index]  # Get staff email from mapping
                    assigned_staff.append(staff_email)  # Add email to the list for this time slot

            # Join the emails into a single string, separated by commas
            export_dict_weekly[days_of_week[day_index]][hour_index] = ", ".join(assigned_staff)

    # Create a DataFrame from the dictionary and export it as a CSV
    export_df_weekly = pd.DataFrame(data=export_dict_weekly, index=hours_of_day)
    detail_path = Path(f"outputs/weekly_assignments/{config['class']}_assignments_week{week_num}.csv")
    export_df_weekly.to_csv(detail_path, index=True, index_label="Hour")
    logger.info("Wrote detailed assignment CSV to %s", detail_path)


    print_header("[ ---- Done! ---- ]")
    print_subheader(f"Summary CSV : {summary_path}")
    print_subheader(f"Weekly grid : {detail_path}")


    # Ask for user approval to go to schedule calendar events
    approval = input("\nSend Google Calendar events now? (y/n): ").strip().lower()
    if approval == 'y':
        calendar_events_from_csv(config, week_num)
    # Ask for user approval to run scheduler again
    approval = input("Schedule another week? (y/n): ").strip().lower()
    if approval == 'y':
        run_scheduler(config, demand, availabilities)
    else:
        "ok byeee!!"
        sys.exit(0)


def _load_fixed_ta_assignments(config: dict[str, str]) -> dict[str, dict[str, list[str]]]:
    """
    Load fixed TA assignments keyed by day and hour.

    Returns a mapping of {day: {hour: [emails]}}.
    """
    fixed_path = config.get("fixed_tas")
    if not fixed_path:
        return {day: {} for day in calendar_time.DAYS}

    csv_path = paths.CONFIG_DIR / fixed_path
    if not csv_path.exists():
        logging.getLogger(__name__).warning(
            "Fixed TA roster %s was not found; proceeding without fixed assignments.",
            csv_path,
        )
        return {day: {} for day in calendar_time.DAYS}

    fixed_assignments: dict[str, dict[str, list[str]]] = {day: {} for day in calendar_time.DAYS}
    with csv_path.open(newline="") as fixed_file:
        reader = csv.DictReader(fixed_file)
        for row in reader:
            hour = row.get("Hour")
            if not hour:
                continue
            for day in calendar_time.DAYS:
                cell = row.get(day, "")
                if not cell:
                    continue
                emails = [
                    email.strip()
                    for email in cell.split(",")
                    if email.strip()
                ]
                if emails:
                    fixed_assignments[day][hour] = emails
    return fixed_assignments


def _calculate_week_start(config: dict[str, str], week_num: int) -> datetime:
    """Calculate the Monday of the requested week, accounting for weeks skipped."""
    base_start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    weeks_skipped = int(config.get("weeks_skipped", 0))
    return base_start_date + timedelta(weeks=week_num - 1 - weeks_skipped)


def _parse_assignments_from_csv(
    csv_name: str,
    config: dict[str, str],
    week_num: int,
    include_fixed_tas: bool,
) -> list[dict[str, object]]:
    """Parse assignments from the CSV export and optionally merge fixed TA requirements."""
    week_start = _calculate_week_start(config, week_num)
    day_to_date = calendar_time._get_week_dates(week_start)  # pylint: disable=protected-access
    fixed_assignments = _load_fixed_ta_assignments(config) if include_fixed_tas else {day: {} for day in calendar_time.DAYS}

    assignments = []
    with open(csv_name) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            hour = row["Hour"]
            for day in calendar_time.DAYS:
                cell = row.get(day, "")
                attendees: list[str] = []
                if cell:
                    for email in cell.split(","):
                        email = email.strip()
                        if email and email not in attendees:
                            attendees.append(email)

                for email in fixed_assignments.get(day, {}).get(hour, []):
                    if email not in attendees:
                        attendees.append(email)

                if not attendees:
                    continue

                start_time_str = f"{day_to_date[day].strftime('%Y-%m-%d')}T{hour}:00"
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
                end_time = start_time + timedelta(hours=1)

                assignments.append(
                    {
                        "start_time": start_time.strftime('%Y-%m-%dT%H:%M'),
                        "end_time": end_time.strftime('%Y-%m-%dT%H:%M'),
                        "attendees": attendees,
                        "day": day,
                        "hour_key": start_time.strftime('%H:%M'),
                    }
                )

    return assignments


def load_weekly_demand_metadata(config, week_num):
    """Load demand sheet metadata for the specified week keyed by (day, hour)."""

    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    values = utils.get_sheet_values(demand_id, config["DEMAND_RANGE"])

    metadata = {}
    current_weeks = []
    current_day = None

    for row in values:
        if not row or len(row) < 4:
            continue

        if row[0]:
            weeks_str = row[0].strip()
            current_weeks = [int(week.strip()) for week in weeks_str.split(",") if week.strip()]

        if week_num not in current_weeks:
            continue

        if row[1]:
            current_day = row[1].strip()

        if not current_day:
            continue

        start_label = row[2].strip() if len(row) > 2 else ""
        if not start_label:
            continue

        try:
            hour_key = datetime.strptime(start_label, "%I:%M %p").strftime("%H:%M")
        except ValueError:
            continue

        location = row[5].strip() if len(row) > 5 else ""
        description = row[6].strip() if len(row) > 6 else ""
        total_staff = row[7].strip() if len(row) > 7 else ""
        comments = row[8].strip() if len(row) > 8 else ""

        metadata[(current_day, hour_key)] = {
            "location": location,
            "description": description,
            "total_staff": total_staff,
            "comments": comments,
        }

    return metadata


def _print_assignment_summary(assignments, csv_name):
    """Print a quick summary of pulled assignments before creating events."""
    if not assignments:
        return

    start_date = min(
        (datetime.strptime(a['start_time'], '%Y-%m-%dT%H:%M') for a in assignments if a['attendees']),
        default=None,
    )
    end_date = max(
        (datetime.strptime(a['end_time'], '%Y-%m-%dT%H:%M') for a in assignments if a['attendees']),
        default=None,
    )

    unique_tas = []
    for assignment in assignments:
        for attendee in assignment['attendees']:
            if attendee not in unique_tas:
                unique_tas.append(attendee)

    tas_sample = ", ".join(unique_tas[:5]) if unique_tas else "No TAs found"

    print(f"\nFound \033[1m{len(assignments)} assignments\033[0m in CSV file: \033[1m{csv_name}\033[0m\n")
    if start_date and end_date:
        print(f"\033[1mSpanning dates:\033[0m\n{start_date.strftime('%A, %B %d, %Y')} - {end_date.strftime('%A, %B %d, %Y')}\n")
    print(f"\033[1mUnique TAs ({len(unique_tas)} total), including:\033[0m\n{tas_sample}")


def calendar_events_from_csv(config, week_num):
    """
    Creates Google Calendar events based on assignments from a CSV file.

    Parameters:
    ----------
    config : dict
        The configuration produced by config_read.read_config, e.g. from configs/61A_config.json.

    week_num : int
        Week of the semester for which the events are scheduled.

    Process:
    --------
    - Loads assignments from the CSV file for the given week.
    - Verifies with the user that the details are correct (dates, number of TAs, etc.).
    - Fetches the calendar name to confirm the correct calendar.
    - Creates calendar events for each assignment

    Notes:
    ------
    - Ensure the CSV is correctly formatted (one row per hour, TA emails in columns for each day).
    - OAuth authentication must be handled by `calendar_time.authenticate()` in the calendar_time.py file
    - Google Calendar is picky about datetime format, so watch out for that.
    """

    logger = logging.getLogger(__name__)

    # Construct the CSV file path based on the selected class and week number
    csv_name = f"outputs/weekly_assignments/{config['class']}_assignments_week{week_num}.csv"

    # Check if the CSV file exists
    if not os.path.exists(csv_name):
        print(f"ERROR: CSV file {csv_name} not found. Please generate the CSV file and try again.")
        logger.error("Assignment CSV %s not found", csv_name)
        sys.exit(1)

    include_fixed_tas = False
    fixed_path = config.get("fixed_tas")
    if fixed_path:
        csv_path = paths.CONFIG_DIR / fixed_path
        if csv_path.exists():
            choice = input(
                f"Include fixed TAs from {fixed_path}? (y/n): "
            ).strip().lower()
            include_fixed_tas = choice == 'y'
        else:
            logger.warning("Configured fixed_tas file %s not found.", csv_path)

    assignments = _parse_assignments_from_csv(csv_name, config, week_num, include_fixed_tas)
    if not assignments:
        print("No assignments with attendees found; aborting calendar export.")
        logger.warning("No assignments extracted from %s for week %s.", csv_name, week_num)
        return []

    _print_assignment_summary(assignments, csv_name)

    print("\n\033[1mEvent Details:\033[0m")
    print(f"Events will be named: {config['calendar_event_name']}")
    print(f"Location: {config['calendar_event_location']}")
    print(f"Description: {config['calendar_event_description']}")
    print(f"Calendar ID: {config['calendar_id']}")

    final_approval = input("\nEnter 'y' to continue or 'n' to quit: ").strip().lower()
    if final_approval != 'y':
        print("Good-bye!")
        return []

    demand_metadata = load_weekly_demand_metadata(config, week_num)
    calendar_time.send_assignments_to_calendar(assignments, config, demand_metadata)

    return assignments



if __name__ == '__main__':
    main()

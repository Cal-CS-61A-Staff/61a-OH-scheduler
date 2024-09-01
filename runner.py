import config_read
import send_email
import utils
import State
import os, sys
import numpy as np
<<<<<<< HEAD
import shutil
from datetime import timedelta
import re
=======
# from datetime import timedelta
# #from google.cloud import storage
>>>>>>> 05a62e4 (ugh)

from google.api_core.exceptions import Forbidden, NotFound
import validation
import algorithm
import pandas as pd


<<<<<<< HEAD

=======
>>>>>>> 05a62e4 (ugh)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# Function to get user approval for the google sheets links
def get_user_approval(label, link):
    while True:
        print(f"{label} found in config.json: {link}")
        approval = input("Is this correct? (y/n): ").strip().lower()
        if approval == 'y':
            return link
        elif approval == 'n':
            return input(f"Please enter the correct {label.lower()}: ").strip()
        else:
            print("Invalid input, please enter 'y' or 'n'.")


def main():

    print("\n\033[1m[---- Welcome to the Office Hours Scheduler! ---- ]\033[0m\n")


    # Step 1: Read the config file
    config = config_read.read_config("config.json")
    
    # Step 2: Print links and ranges for user approval
    print("\033[1m[ ---- Current Settings: ---- ]\033[0m\n")
    print(f"Availabilities Sheet Link: \n{config['availabilities_link']}\n")
    print(f"Demand Sheet Link: \n{config['demand_link']}")
    print("\nRelevant Sheet Ranges:")
    print(f"- AVAILABILITIES_RANGE = '{config['AVAILABILITIES_RANGE']}")
    print(f"- DEMAND_RANGE = '{config['DEMAND_RANGE']}'")

    # Ask for user approval
    approval = input("\n\033[1mDoes everything look correct? (y/n): \033[0m").strip().lower()
    if approval != 'y':
        print("Please edit config.json, then re-run the program.")
        sys.exit(1)

    AVAILABILITIES_RANGE = config["AVAILABILITIES_RANGE"]
    DEMAND_RANGE = config["DEMAND_RANGE"]

    # Step 3: Fetch and validate availabilities data
    availabilities_id = config_read.get_google_sheets_id(config["availabilities_link"])
    availabilities = utils.get_availabilities(availabilities_id, AVAILABILITIES_RANGE)
    validation.validate_availabilities(availabilities)

    # Step 4: Fetch and validate demand data
    demand_id = config_read.get_google_sheets_id(config["demand_link"])
    demand = utils.get_demand(demand_id, DEMAND_RANGE, config["weeks"])

    # Step 5: Validate the entire config
    validation.validate_config(config)
    # Step 5: Prompt user to enter the current week
    while True:
        try:
            week_num = int(input("Enter the current week number you'd like to run the algo on.\n(e.g., enter 5 to schedule for week 5 of the semester): ").strip())
            if week_num <= 0:
                raise ValueError
            latest_week = week_num - 1
            break
        except ValueError:
            print("Invalid input, please enter a positive integer for the week number.")


    if (latest_week- config["weeks_skipped"]) > 0:
         print("found state for previous week: ", latest_week)
         last_state = utils.deserialize(latest_week, config["weeks_skipped"])
    else:
        last_state = None
    
    if last_state and last_state.week_num == config["weeks"]:
        print(f"ERROR: The algorithm has already been run for all weeks. The last state was for week {config['weeks']}. Exiting.")
        return
    if latest_week == config['weeks']:
        raise RuntimeError("Allotted # of weeks have already passed. Exiting.")

    # Create new state object
    state = State.State(last_state, 
                        demand, 
                        availabilities, 
                        config["class"], 
                        config["semester"], 
                        config["weeks"], 
                        config["weekly_hour_multiplier"], 
                        config["weeks_skipped"])
    
    # Run algorithm
    inputs = state.get_algo_inputs()
    assignments = algorithm.run_algorithm(inputs)
    # \assignments = np.load("assignments.npy")[:, 0, :, :]

    np.save('demand.npy', demand)

    state.set_assignments(assignments)

    print()
    # Create CSV export of the next week's assignments
    export_dict = {"email": [], "hours_assigned": []}
    for i in range(assignments.shape[0]):
        if assignments[i].sum() != 0:

            export_dict['email'].append(state.bi_mappings.inverse[i])
            export_dict['hours_assigned'].append(assignments[i].sum())

    export_df = pd.DataFrame(data=export_dict)
    export_df.to_csv(f"outputs/hours_assigned_week{week_num}.csv", index=False)
    

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
    export_df_weekly.to_csv(f"outputs/weekly_assignments/assignments_week{state.week_num}.csv", index=True, index_label="Hour")

    # Validate algorithm output TODO

    # Email send
    # mappings = state.bi_mappings
    # first_monday = utils.nearest_future_monday(config["start_date"])
    # starting_monday = first_monday + timedelta((state.week_num - config["weeks_skipped"] - 1)* 7)
    
    # for i in range(assignments.shape[0]):
    #     email = mappings.inverse[i]
    #     send_email.send_invites(email, 
    #                           assignments[i], 
    #                           starting_monday, 
    #                           config["calendar_event_name"], 
    #                           config["calendar_event_location"], 
    #                           config["calendar_event_description"])
    
    state.serialize() #save the current state as a pickle
    print("\n\033[1m[ ---- Done! ---- ]\033[0m\n") 
    print("Check the outputs folder for the results.")

if __name__ == '__main__':
    main()

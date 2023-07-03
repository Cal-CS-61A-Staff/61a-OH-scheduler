# OH Scheduler Platform Design Document
Author: Cyrus Hung

## 1. Classes and Data Structures

### State.py

#### Fields
prev_state
- Reference to the deserialized previous state. None if this is the first time.

week_num
- The current week this State object represents

weeks_remaining
- The number of weeks remaining in the semester, including this week
E.g. for a 13-week semester, if this State object is produced in between week 1 and week 2, then weeks_remaining should be 12 as only 1 week has actually been completed

state_df 
- Dataframe with the following columns:
    - Email address
    - Availability
        - Np array of shape (5, 12)
    - Number of of allotted hours remaining

this_weeks_assignments
- Np array of shape (# of staff, 5, 12) representing the assignments for this week 
- If assignments haven't been calculated yet, this will be None

non_day_ones
- Email addresses of staff members who were not originally added to the algorithm for the first week

row_last_read
- String representing which row in the google sheet we stopped on for this state.
#### Methods


## 2. Algorithms

1. Config Read parses config.json and gets all data. Validate to ensure no field is empty, links work, and that weekly hour multiplier is above 1. Return error message if something is wrong
2. Links from config read are sent to State, which does additional validation against previous state objects (TODO: what things should be validated against previous state?). 
    1. Initialize state_df with prev_state's state_df
    1. Use prev_state's row_last_read to resume reading new rows (ASSUMPTION: No one will edit the google sheets directly, and if changes need to be made they will always fill out the form again.)
    1. When reading new rows, 


### User workflow
1. Fill in config_read json
- "availabilities_link": Make a copy of OH availabilities google form, create a linked google sheets, and use that link.
- "demand_link": make a copy of OH demand google sheets, fill in information. Put sheet URL in config.json
- "path_to_bucket": create a folder for storing states objects and other intermediate results. Link relative path.
- "class": fill in a string for what class this output is for (e.g. "cs61a")
- "weeks": fill in an int for total number of weeks in a semester
- "weekly_hour_multiplier": fill in a float representing the multiplier for the max amount of hours per person. This number is used to multiply with the target number of office hours assigned per week to determine the maximum number of hours they can be assigned in a week. Default: 2 (change it to 1 if you'd like students always being assigned their target number of hours each week.) VALIDATION: MUST BE 1+
1. Make a copy of OH availabilities google form and link google sheets. Put sheet URL in config.json
2. Make a copy of OH demand google sheets, fill in information. Put sheet URL in config.json
3. Follow https://developers.google.com/sheets/api/quickstart/python in order to create credentials for accessing the sheets using the google sheets API.
4. Create a folder for intermediate objects (states, etc.) copy the relative location to that folder into config.json (Path to Bue)
5. Run starter function

## 3. Persistence

## 4. Design Diagram

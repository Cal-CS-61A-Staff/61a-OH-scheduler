from __future__ import print_function
import os.path
import utils
import numpy as np
import pickle
import copy
from bidict import bidict
from google.cloud import storage
import io

class StaffMember:
    """
    Represents an individual course staff member
    """

    # Indices of the data in the availabilities spreadsheet. WARNING: If the form is changed,
    # these indices must be updated.
    EMAIL_ADDRESS_INDEX = 0
    APPOINTED_POSITION_INDEX = 1
    TOTAL_WEEKLY_HOURS_INDEX = 2 # the number of hours per week a staff member's total appointment is
    SEMESTERS_ON_STAFF_INDEX = 3
    SEMESTER_AS_AI_INDEX = 4
    WEEKLY_OH_HOURS_INDEX = 5
    PREFERRED_CONTIGUOUS_HOURS_INDEX = 6
    AVAILABILITIES_INDICES = range(7, 67) # 5 * 12 slots

    def __init__(self, data_row, weeks_left):
        """Initializes a new StaffMember object.

        Instance Attributes:
            email (string): The email address of the course staff member.
            weekly_oh_hours (int): The number of office hours the course staff member is expected to work per week.
            preferred_contiguous_hours (int): The number of contiguous hours the course staff member prefers to work.
            availabilities (np.array): A 5x12 np array of the course staff member's availabilities.
            assigned_hours (np.array): A 5x12 np array of the course staff member's
            assigned hours. Assigned only after the algorithm is run. 
            hours_left (int): The number of office hours left to assign to this course
            staff member this semester.

            NOTE: The following aren't used, and are here for future reference:
            appointed_position (string): The appointed position of the course staff member.
            total_weekly_hours (int): The total number of hours the course staff member is expected to work per week.
            semesters_on_staff (int): The number of semesters the course staff member has been on staff.
            semesters_as_ai (int): The number of semesters the course staff member has been an AI.
    
        Args:
            data_row (list): A row from the availabilities spreadsheet. The
            first element is the email address, and the rest are relevant data.
            The indices of the row that correspond to the availabilities,
            preferred hours, appointed hours, etc. are specified as class variables.
            weeks_left (int): The number of weeks left in the semester, INCLUDING the week this state is made for.
        """
        self.email = data_row[StaffMember.EMAIL_ADDRESS_INDEX]
        self.weekly_oh_hours = int(data_row[StaffMember.WEEKLY_OH_HOURS_INDEX])
        self.preferred_contiguous_hours = int(data_row[StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX])

        # Extract number from availabilities list and reshape
        availabilities_list = [data_row[i] for i in StaffMember.AVAILABILITIES_INDICES]
        self.availabilities = utils.create_5x12_np_array(availabilities_list)

        self.hours_left = weeks_left * self.weekly_oh_hours

        # To be filled by the algorithm after it's done running
        self.assigned_hours = None

        # The following aren't used, and are here for future reference
        self.appointed_position = data_row[StaffMember.APPOINTED_POSITION_INDEX]
        self.total_weekly_hours = int(data_row[StaffMember.TOTAL_WEEKLY_HOURS_INDEX])
        self.semesters_on_staff = int(data_row[StaffMember.SEMESTERS_ON_STAFF_INDEX])
        self.semesters_as_ai = int(data_row[StaffMember.SEMESTER_AS_AI_INDEX])

    def update(self, data_row, weeks_left):
        """Updates the information for a course staff.

        Args:
            new_row (list): A row from the availabilities spreadsheet.
            weeks_left (int): The number of weeks left in the semester, INCLUDING the week this state is made for.
        """
        if data_row[StaffMember.EMAIL_ADDRESS_INDEX] != self.email:
            raise Exception("Email addresses do not match")
        
        # Replace old data with no special instructions
        self.appointed_position = data_row[StaffMember.APPOINTED_POSITION_INDEX]
        self.total_weekly_hours = int(data_row[StaffMember.TOTAL_WEEKLY_HOURS_INDEX])
        self.semesters_on_staff = int(data_row[StaffMember.SEMESTERS_ON_STAFF_INDEX])
        self.semesters_as_ai = int(data_row[StaffMember.SEMESTER_AS_AI_INDEX])
        self.preferred_contiguous_hours = int(data_row[StaffMember.PREFERRED_CONTIGUOUS_HOURS_INDEX])

        # if the weekly oh hours changed, we replace the hours left with just the new value * weeks left
        # otherwise we keep it as the old hours_left count. This is to prevent situations where students
        # resubmit the form and their hours_left count gets "reset".
        if self.weekly_oh_hours != int(data_row[StaffMember.WEEKLY_OH_HOURS_INDEX]):
            self.weekly_oh_hours = int(data_row[StaffMember.WEEKLY_OH_HOURS_INDEX])
            self.hours_left = weeks_left * self.weekly_oh_hours

        # Reshape availabilities list
        availabilities_list = [data_row[i] for i in StaffMember.AVAILABILITIES_INDICES]
        self.availabilities = utils.create_5x12_np_array(availabilities_list)

    def set_assignment(self, assignment):
        """
        Given an np_array of size 5x12, representing the assignment for this
        week, sets the assignment for this StaffMember and decreases their
        remaining hours. This should be run once per state after the algorithm
        is finished running.

        Args:
            assignment (np.array): 5x12 np array representing this staff's assignment for the week.
        """
        self.assigned_hours = assignment
        self.hours_left -= np.sum(assignment)

    def calculate_availabilities_difference(self, other_availability):
        """
        Calculates the difference between this StaffMember's availabilities and
        another availabilities array. The difference is defined with this formula:
        Convert both availabilities matrices to boolean values: (1-4 is 1, 5 is
        0). Let X’ be the input availabilities and X be the staff’s
        availabilities. Return (X - X’).sum((1, 2)). The difference is then divided
        by the boolean sum of the other_availability matrix.

        Args:
            other_availability (np_array): The other availabilities array to compare to.

        Returns:
            difference (int): The difference score, defined by (X - X’).sum((1, 2))/sum(X')
        """

        this_converted = np.where(self.availabilities == 5, 0, 1)
        other_converted = np.where(other_availability == 5, 0, 1)

        return np.sum(this_converted - other_converted)/np.sum(other_converted)

    def __str__(self) -> str:
        info = "Course Staff Student:\n"
        info += "Email: {}\n".format(self.email)
        info += "Weekly Office Hours: {}\n".format(self.weekly_oh_hours)
        info += "Preferred Contiguous Hours: {}\n".format(self.preferred_contiguous_hours)
        info += "Availabilities:\n{}\n".format(self.availabilities)
        info += "Hours Left: {}\n".format(self.hours_left)
        info += "Assigned Hours:\n{}\n".format(self.assigned_hours)
        info += "Appointed Position: {}\n".format(self.appointed_position)
        info += "Total Weekly Hours: {}\n".format(self.total_weekly_hours)
        info += "Semesters on Staff: {}\n".format(self.semesters_on_staff)
        info += "Semesters as AI: {}\n".format(self.semesters_as_ai)

        return info
        
    
class state:
    """
    An internal state object for storing relevant information between runs. 
    There should be one state for each week that this algorithm has been run.
    The state's week number (and name) represents the week that this state is being run for,
    e.g. the upcoming week for which the algorithm is run for.
    """
    
    def __init__(self, prev, oh_demand, availabilities, class_name, semester, total_weeks, max_weekly_multiplier, weeks_skipped):
        """Initializes a new state object

        Args:
            prev (string, optional): location to the previous serialized State structure (None if this is the first week). Defaults to None.
            oh_demand (np array): (total weeks - weeks_skipped)x5x12 np array representing the demand for office hours for all weeks.
            availabilities_sheet (string): 
            intermediate_folder (string): 
            class_name (_type_): _description_
            semester (_type_): _description_
            total_weeks (_type_): _description_
            max_weekly_multiplier (_type_): _description_

        Instance Variables:
            prev_state (state): List of all previous State objects.
            week_num (int): The current week this State object represents. 
            weeks_remaining (int): The number of weeks remaining in the semester, including this week.
            state_df (pd.DataFrame): Dataframe with the following columns:
                - Email address
                - Availability (Np array of shape (5, 12))
                - # of allotted hours remaining
                - this_weeks_assignments (Np array of shape (# of staff, 5, 12) representing the assignments for this week)
                    If assignments haven’t been calculated yet, this will be None.
            non_day_ones (list): Email addresses of staff members who were not originally added to the algorithm for the first week.
            rows_parsed (int): The number of rows from the availabilities sheet values visited so far.

        Returns:
            state: state object with pertinent information filled in
        """
        # If prev is None, this is the first state object.
        if not prev:
            self.prev_state = None
            self.week_num = weeks_skipped + 1
            self.weeks_remaining = total_weeks - weeks_skipped
            self.StaffMember_dict = {}
            self.bi_mappings = bidict({})
            self.rows_parsed = 0

            self.update(availabilities, self.weeks_remaining)
            self.day_ones = len(self.StaffMember_dict)
        else:
            self.prev_state = prev
            self.week_num = prev.week_num + 1 
            self.weeks_remaining = prev.weeks_remaining - 1
            self.rows_parsed = prev.rows_parsed
            self.StaffMember_dict = copy.deepcopy(prev.StaffMember_dict)
            self.bi_mappings = copy.deepcopy(prev.bi_mappings)
            self.day_ones = prev.day_ones

            # update availabilities dataframe
            self.update(availabilities, self.weeks_remaining)

        self.oh_demand = oh_demand
        self.max_weekly_multiplier = max_weekly_multiplier
        self.class_name = class_name
        self.semester = semester
        self.weeks_skipped = weeks_skipped
        return None
    


    def update(self, availabilities, weeks_remaining):
        """Given the staff availabilities sheet, update state and each course staff.

        Args:
            availabilities (list): list of lists, each list representing a student in the availabilities sheet.
            weeks_remaining (int): the number of weeks left in the semester including the week this state is made for.
        """

        # Update each student after last_parsed_row
        new_form_submissions = availabilities[self.rows_parsed:]
        latest_form_submissions = utils.filter_last_row_by_email(new_form_submissions)
        for student_list in latest_form_submissions:
            # Extract email address
            email = student_list[StaffMember.EMAIL_ADDRESS_INDEX]

            # If the email address is not in mappings, create a new student, mappings, and add to list
            if email not in self.StaffMember_dict:
                staff = StaffMember(student_list, weeks_remaining)
                self.StaffMember_dict[email] = staff
                self.bi_mappings[email] = len(self.StaffMember_dict) - 1
            else:
                # Update the corresponding student.
                self.StaffMember_dict[email].update(student_list, weeks_remaining)

            self.rows_parsed += 1
    
    def set_assignments(self, assignments):
        """Sets the assignments for this week, decreases the hours left for each staff member.

        Args:
            assignments (np.array): Np array of shape (# of staff, 5, 12) representing the assignments for this week.
            Each row's index should match up with bi_mappings for which staff member it refers to
        """
        if assignments.shape[0] != len(self.StaffMember_dict):
            raise ValueError("Assignments length does not match number of staff members. {} != {}".format(assignments.shape[0], len(self.StaffMember_dict)))

        for i in range(len(assignments)):
            assignment = assignments[i]
            staff_email = self.bi_mappings.inverse[i]
            self.StaffMember_dict[staff_email].set_assignment(assignment)

    def get_day_one_assignments(self):
        """Returns all past assignments of day one staff memberes

        Returns:
            np.array: Np array of shape (# of previous weeks, # of day one staff, 5, 12) representing the assignments for each previous week.
        """
        results = []
        current = self.prev_state
        if not current:
            return np.array([])
        while current:
            assignments = []
            for i in range(self.day_ones):
                staff_email = current.bi_mappings.inverse[i]

                if staff_email != self.bi_mappings.inverse[i]:
                    raise ValueError("mappings do not match up between states")
                
                staff = current.StaffMember_dict[staff_email]

                assignments.append(staff.assigned_hours)
            results.append(np.stack(np.array(assignments), axis=0))
            current = current.prev_state
        results = np.array(results)
        if len(results) > 1:
            results = np.stack(np.array(results), axis=0)
        if results.shape != (self.week_num - self.weeks_skipped - 1, self.day_ones, 5, 12):
            raise ValueError("results shape does not match up with expected shape. {} != {}".format(results.shape, (self.week_num - self.weeks_skipped - 1, self.day_ones, 5, 12)))
        
        return results

    
    def get_algo_inputs(self):
        """
        Returns:
            list: list of all inputs required for the algorithm:
                - OH demand np array (np_array [# future weeks, 5, 12]):
                    - Most up-to-date version of the OH demand spreadsheet output for all weeks in the future INCLUDING the week this state is made for.
                - Prev_assignments: (np_array[# of past states, # of day one staff, 5, 12]):
                - Availabilities (np_array[# all staff, 5, 12]):
                - Max_hours (np_array[# all staff]): 
                - Hours_remaining (np_array[# all staff]):
                - preferred_contiguous_hours(np_array[# all staff]): 
                - changed_hours(np_array[# of day one staff]):
                - Non_day_one_indices:
        """

        future_oh_demand = self.oh_demand.take(list(range(self.week_num - 1, self.week_num + self.weeks_remaining - 1)), axis=0)

        # run sanity check on indices
        self.validate_mappings()

        # collect each state's staff assignments
        previous_assignments = self.get_day_one_assignments()

        current_availabilities = np.array([None] * len(self.StaffMember_dict))
        for email in self.bi_mappings:
            index = self.bi_mappings[email]
            current_availabilities[index] = self.StaffMember_dict[email].availabilities
        if len(current_availabilities) > 1:
            current_availabilities = np.stack(current_availabilities)

        max_hours = np.array([None] * len(self.StaffMember_dict))
        hours_remaining = np.array([None] * len(self.StaffMember_dict))
        preferred_contiguous_hours = np.array([None] * len(self.StaffMember_dict))
        for email in self.bi_mappings:
            index = self.bi_mappings[email]
            max_hours[index] = self.StaffMember_dict[email].preferred_contiguous_hours * self.max_weekly_multiplier
            hours_remaining[index] = self.StaffMember_dict[email].hours_left
            preferred_contiguous_hours[index] = self.StaffMember_dict[email].preferred_contiguous_hours
        if len(self.StaffMember_dict) > 1:
            max_hours = np.stack(max_hours)
            hours_remaining = np.stack(hours_remaining)
            preferred_contiguous_hours = np.stack(preferred_contiguous_hours)
        
        if self.prev_state:
            changed_hours = np.array([None] * self.day_ones)
            for i in range(self.day_ones):
                email = self.bi_mappings.inverse[i]
                changed_hours[i] = self.StaffMember_dict[email].calculate_availabilities_difference(self.prev_state.StaffMember_dict[email].availabilities)
            if len(changed_hours) > 1:
                changed_hours = np.stack(changed_hours)
        else:
            changed_hours = np.array([0] * self.day_ones)

        non_day_one_indices = np.array(list(range(self.day_ones, len(self.StaffMember_dict))))
        return [
            future_oh_demand,
            previous_assignments,
            current_availabilities,
            max_hours,
            hours_remaining,
            preferred_contiguous_hours,
            changed_hours,
            non_day_one_indices
        ]
    
    def validate_mappings(self):
        """
        As having wrong bi_mappings results in invisible bugs, this function is used to check that the bi_mappings are correct.
        Through comparing the bi_mappings to the all prev_state bi_mappings.
        """
        prev = self.prev_state
        while prev:
            for email in self.bi_mappings:
                # Must be a new email, skip.
                if email not in prev.bi_mappings:
                    continue
                if prev.bi_mappings[email] != self.bi_mappings[email]:
                    raise ValueError("bi_mappings do not match up between states. Stop.")
            prev = prev.prev_state
        
    def serialize(self, project_id, bucket_name, prefix=None):
        """Saves this object using pickle. Prev_state should not be referenced while this is serializing.
        As all previous states are deserialized as a result of this state being serialized, we recursively
        serialize each previous state as well.

        Returns:
            None
        """
        if self.prev_state:
            self.prev_state.serialize(project_id, bucket_name, prefix)
        place_holder = self.prev_state
        self.prev_state = None
        object_name = '{}/{}.pkl'.format(prefix, self.week_num)

        # Initialize a Google Cloud Storage client
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.get_bucket(bucket_name)

        try:
            blob = storage.Blob(object_name, bucket)
            blob.delete()
        except Exception as e:
            print(f"Creating new blob for {object_name}.")

        try:
            # Pickle the Python object to a byte stream
            byte_stream = io.BytesIO()
            pickle.dump(self, byte_stream)
            
            # Reset stream position to the beginning and upload
            byte_stream.seek(0)
            blob = bucket.blob(object_name)
            blob.upload_from_file(byte_stream)
            print("State object uploaded successfully.")
        except Exception as e:
            print(f"Something went wrong while serializing state #{self.week_num}. Error: {str(e)}")
        finally:
            self.prev_state = place_holder
    
    def __str__(self):
        prev_state_str = str(self.prev_state.week_num) if self.prev_state else "None"
        email_keys = list(self.StaffMember_dict.keys())
        bi_mappings_str = str(dict(self.bi_mappings)) + ", Inverse: " + str(dict(self.bi_mappings.inverse))
        oh_demand_str = np.array2string(self.oh_demand, precision=2, separator=',', suppress_small=True)

        return (
            f"Class name: {self.class_name}\n"
            f"Semester: {self.semester}\n"
            f"Previous state: {prev_state_str}\n"
            f"Week number: {self.week_num}\n"
            f"Weeks remaining: {self.weeks_remaining}\n"
            f"Course staff email keys: {email_keys}\n"
            f"Bi-directional mappings: {bi_mappings_str}\n"
            f"Rows parsed: {self.rows_parsed}\n"
            f"Day ones: {self.day_ones}\n"
            f"OH demand: {oh_demand_str}\n"
            f"Max weekly multiplier: {self.max_weekly_multiplier}\n"
        )

    def print_algo_outputs(self):
        values = self.get_algo_inputs()
        for i in range(len(values)):
            values[i] = np.array2string(values[i], precision=2, separator=',', suppress_small=True)

        print(
            f"OH demand: {values[0]}\n",
            f"Previous assignments: {values[1]}\n",
            f"Availabilities: {values[2]}\n",
            f"Max hours: {values[3]}\n",
            f"Hours remaining: {values[4]}\n",
            f"Preferred contiguous hours: {values[5]}\n",
            f"Changed hours: {values[6]}\n",
            f"Non day one indices: {values[7]}\n"
        )
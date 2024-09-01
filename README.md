# 61a-OH-scheduler
Machine Driven Scheduler <br>
<img src="https://github.com/Cal-CS-61A-Staff/61a-OH-scheduler/assets/40013378/0ea38fcf-2879-4982-816f-34f2463b310a" alt="drawing" width="350"/>


# Setting up the OH Scheduler for CS61A
### *(the following written by shm)*

1. log into the CS61A SPA account
2. make copies of the Availabilities Sheet and Demands Sheet for working with
3. clone this git repo - now you have a working directory, but the project doesn’t come with credentials - the files that would tell Google our code should have the permission to access and read our Google Sheets and make calendar events. That’s because it would be not great to share such files on a GitHub lol so…. 
4. …. let’s get our project access to those google sheets! 
---
1. Log into the Google Cloud Console from the CS61A SPA account.
    - I have enabled the Google Sheets API for the “CS61A Website Google Cloud Project” so you probably don’t have to do that again, unless you’d like to use a different “project” ?
2. Click on **IAM & Admin** and hopefully you should see a page with the title **"Permissions for project "CS 61A Website”**
    1. hopefully you see this “service account”: “[oh-scheduler@cs-61a-website.iam.gserviceaccount.com](mailto:oh-scheduler@cs-61a-website.iam.gserviceaccount.com)” 
        - this is the username for our Bot. You want to give our Bot access to the Google Sheets. So literally copy this email, go into both the Availabilities and Demand sheets, hit the Share button, and ***add this email address to the list of users the sheets are shared with!***
3. next, (in the Google Cloud Console) click on **KEYS** 
    1. click ADD KEY > Create New Key > JSON > Create
    2. This should prompt a download of a .JSON file to your computer. You should save it to the working directory as ***credentials.json*** 
        1. fun fact: you cannot download it ever again after this point! but you can always make a new key and delete the old one.
            
            ```json
            {
              "type": "service_account",
              "project_id": "cs-61a-website",
              "private_key_id": "****",
              "private_key": "-----BEGIN PRIVATE KEY-----\***\n-----END PRIVATE KEY-----\n",
              "client_email": "oh-scheduler@cs-61a-website.iam.gserviceaccount.com",
              "client_id": "*******",
              "auth_uri": "https://accounts.google.com/o/oauth2/auth",
              "token_uri": "https://oauth2.googleapis.com/token",
              "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
              "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/oh-scheduler%40cs-61a-website.iam.gserviceaccount.com",
              "universe_domain": "googleapis.com"
            }
            
            ```
            

Yay we now the service account has access to the Google Sheets it needs... AND our code has a credentials file that gives it access to the “[oh-scheduler@cs-61a-website.iam.gserviceaccount.com](mailto:oh-scheduler@cs-61a-website.iam.gserviceaccount.com)” Service Account!


time to start running code…

1. install requirements 

`pip install -r requirements.txt`
`pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib`

2. update config.json
    - replace the sheet URLs, starting date, semester, etc.
3.    check out where it says:
  
        
        ```python
        AVAILABILITIES_RANGE = 'Form Responses 1!B1:BQ'
        DEMAND_RANGE = 'Demand!A2:E'
        ```
        
    
  now double check that these match the Google Sheets. the syntax here is SheetTitle!Range. Sheet title can be seen in the bottom left corner of Google Sheets, ex "Form Responses 1". 
  
  You can enter the ranges (e.g. B1:BQ) into the top left corner of Google Sheets to check that those ranges are as you expect. 
    
![as of Fall 2024, the range is B1:BQ. it was previously B1:BP, but we added a column for specifying 88C vs 61A](images/image.png)
    
 as of Fall 2024, the range is B1:BQ. it was previously B1:BP, but we added a column for specifying 88C vs 61A.
    
![note that we are ignoring the timestamp column, which means the Email Address Column = the first column = Index 0](images/image%201.png)
    
    
4. Now open up **State.py**
    - Here we have this section of code:
    
    ```python
    # Indices of the data in the availabilities spreadsheet. 
        # First column = 0, second column = 1, etc.
        # WARNING: If the form is changed,
        # these indices must be updated.
        EMAIL_ADDRESS_INDEX = 0
        WHICH_COURSE = 1
        APPOINTED_POSITION_INDEX = 2
        TOTAL_WEEKLY_HOURS_INDEX = 3 # the number of hours per week a staff member's total appointment is
        SEMESTERS_ON_STAFF_INDEX = 4
        SEMESTER_AS_AI_INDEX = 5
        WEEKLY_OH_HOURS_INDEX = 6
        PREFERRED_CONTIGUOUS_HOURS_INDEX = 7
        AVAILABILITIES_INDICES = range(8, 68) # 5 days * 12 hours worth of slots per day  (9AM - 9PM) = 60 slots
    ```
    

these correspond to column order. check that this is the same order as the info in the sheet as well. 

5. once you have checked those things, I wrote a test to check its all working as expected. Try the following commands:
```
> python3
>>> import validation
>>> validation.test()
```

and you should hopefully see a bunch of data from the Google Sheets get printed out, like this:

![data grabbed from availabilities sheet](images/image%202.png)

![data grabbed from demand sheet](images/image%203.png)


6. IF YOU GET AN ERROR INSTEAD it might be because someone put a wEIRD VALUE into the spreadsheet when what we really need is a number!! 
    - go to [utils.py](http://utils.py) and find the **def get_availabilities(sheet_id, range):** function. here is where it tries to turn all the spreadsheet values (which are strings) into integers.
    - I added a bunch of “try” statements that first *attempt* to convert the spreadsheet value into a number… and if it can’t, tries something else / defaults to a number. 
    - NOTE: this is also where I have set the “default” values for stuff. so if we want to change defaults. look here
7. ok now we have validated that all that exists and we have access to it, go ahead and try running our main program: `runner.py`
   
update: I’ve added a command line interface, so now it prompts you nice and cutely:

![image.png](images/image%205.png)

follow the instructions on screen, and eventually it starts running the optimization algorithm. It takes 5-6 minutes to run on my laptop. 

it does this for like 5 minutes, and then when it's done it puts a CSV into the 
`outputs/weekly_assignments/` folder.



NOTE: It seems that previously, this code would save the state into a 'pickle' file and put that in a Google Cloud storage bucket. I changed this to a local folder inside outputs/ called "pickles" because I don't want to set up google cloud storage for like, 16 small files lol 
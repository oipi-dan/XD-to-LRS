import smtplib
from email.message import EmailMessage
import json

import RunConflation
from datetime import datetime

inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\USA_Virginia'
inputMasterLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'
inputOverlapLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_OVERLAP'
inputIntersections = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_intersections'

outputPath = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Output'


# XDFilters are the SQL definition query for the XD layer.  Each one will run as a batch
batches = [
    {
        "Name": "Test_1",
        "XDFilter": "XDSegID = '429100044'"
    },
    {
        "Name": "Test_2",
        "XDFilter": "XDSegID = '429100044'"
    },
    {
        "Name": "Test_3",
        "XDFilter": "XDSegID = '429100044'"
    },
    {
        "Name": "Test_4",
        "XDFilter": "XDSegID = '429100044'"
    },
    {
        "Name": "Test_5",
        "XDFilter": "XDSegID = '429100044'"
    },
    
]


# For sending text alerts when each batch is complete
with open('password.json', 'r') as file:
    data = json.load(file)
    email = data['email']
    password = data['pw']
    receiverEmail = data['receiverEmail']


def send_txt(subject, message):
    try:
        smtp = smtplib.SMTP_SSL('mail.danielfourquet.com', 465)
        smtp.login(email, password)

        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = email
        msg['To'] = receiverEmail

        smtp.send_message(msg)
    except Exception as e:
        print('SEND TXT FAILED')
        print(e)





for batch in batches:
    try:
        batchStart = datetime.now()
        conflationName = batch['Name']
        XDFilter = batch['XDFilter']

        print(f'\n### Starting {conflationName} ###\n')
        RunConflation.start(inputXD, inputMasterLRS, inputOverlapLRS, inputIntersections, conflationName, outputPath, XDFilter)
        batchEnd = datetime.now()
        with open('test.txt', 'a') as file:
            file.write(f'{batchEnd - batchStart}\n')


    except Exception as e:
        print(f"Error processing batch {batch['Name']}")
        print(e)
        send_txt(batch['Name'], 'Failed')

    
    
print(f'\n### Batch Conflation Complete ###\n')
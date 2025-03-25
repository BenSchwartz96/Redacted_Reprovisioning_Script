from xml.dom import minidom
import glob
import os
import mysql.connector
import requests
import json
import logging.handlers
import csv
import sys
import xml.etree.ElementTree as ET

HOST = "REDACTED"
USER = "REDACTED"
PASSWORD = "REDACTED"
PORT = 0000

logger = logging.getLogger('Quota')
hdlr = logging.handlers.TimedRotatingFileHandler('quota.log', when='midnight', interval=1, backupCount=30,
                                                 encoding=None, delay=False, utc=True)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)

pendenzenURL = "REDACTED"
prodisURL = "REDACTED"
preprod_prodisURL = "REDACTED"
headers = {"X-Atlassian-Token": "no-check"}
auth = ('REDACTED', 'REDACTED')

cutoff = 25
reprovision_targets = []


def main():
    """
    Main function for the reprovision_quota.py script. 
    This script is for the purpose of correcting mistakes in Quickline customers NPVR (Network Personal Video Recording) provisioning.
    Mismatches are detected from customer files and fixed. 

    This script has three paths:
    1. Main: Default path that detects mismatches and reprovisions.
    2. Manual: Path for a manual script run. Does not detect mismatches, but reprovisions based on the content of manual_reprovision_targets.csv.
    3. Abort: Path for when the number of misprovisioned customers is above a cutoff. Raises alert and prepares manual_reprovision_targets.csv for manual run.
    """

    # Main branch.
    try:
        manual_run = checkIfManualRun()
        logger.info("reprovision_quota.py has been run. Hello!")
        customers = getLatestCustomerFile()
        NPVR_bundle_data = getNPVR_bundle_data()
        if manual_run == True:
            # Side branch 1: Manual.
            logger.info("Beginning manual branch.")
            readManualTargetList()
            clearManualTargetList()
            startReprovisionLoop(customers, NPVR_bundle_data)
            logger.info("Customer reprovisioning attempts complete. Manual run has concluded. ")
        else:
            # Continuation of main branch. Search for mismatches and then continue or abort.
            findMismatches(customers, NPVR_bundle_data)
            logger.info("Checking number of reprovision targets against cutoff.")
            mismatchCount = len(reprovision_targets)
            if mismatchCount > cutoff:
                # Side branch 2: Abort.
                logger.info(f"Number of reprovision targets exceeds {cutoff}. No automatic reprovision will be attempted.")
                logMismatchedCustomers(mismatchCount)
                writeManualTargetList()
                createNewTicket(mismatchCount)
                logger.info("Script concluding without reprovisioning mismatched customers. A manual script run, by running the script with the '--manual' argument, is required.")
            else:
                # Continuation of main branch: Reprovision mismatched customers.
                startReprovisionLoop(customers, NPVR_bundle_data)
                logger.info("Customer reprovisioning attempts complete.")
    except Exception as e:
        logger.error(f"An error occured during the running of this script. Exception object = {e}")
        sys.exit(1)

# -----------------
# INITIAL FUNCTIONS
# -----------------

def getLatestCustomerFile():
    """
    Fetches the latest customer file, stores the data in variable 'customers', and returns it.

    Returns:
        customers | An xml.dom nodelist where each node represents a customer from the XML file.
    """

    logger.info("Fetching latest customer list from /home/divitel/customerfiles.")
    list_of_files = glob.glob('/home/divitel/customerfiles/*.xml')
    latest_file = max(list_of_files, key=os.path.getctime)
    xml = minidom.parse(latest_file)
    customers = xml.getElementsByTagName("Customer")
    return customers


def getNPVR_bundle_data():
    """
    Fetches data on how many NPVR hours a given bundle should have, and stores this in variable 'NPVR_bundle_data' after converting it to minutes.
    
    Returns:
        NPVR_bundle_data | A list of tuples reflecting the intended NPVR provisioning (in minutes) for each bundle. 
    """

    logger.info("Fetching data on bundles and intended NPVR provisioning.")
    connection = mysql.connector.connect(host=HOST, user=USER, password=PASSWORD, port=PORT)
    myCursor = connection.cursor()
    myCursor.execute("SELECT bundle_id, npvr*60 FROM divitel_config_validator.product_bundle;")
    NPVR_bundle_data = myCursor.fetchall()
    connection.close()
    return NPVR_bundle_data


def checkIfManualRun():
    """
    Checks sys.args to determine if this is a manual run.
    
    Returns either True or False and assigns it to the manual_run variable so the script knows which type of run it is.
    """

    if len(sys.argv) == 1:
        return False
    elif len(sys.argv) == 2 and sys.argv[1] == '--manual':
        logger.info("Script has been run manually. Reprovisioning will occur based on the contents of manual_reprovision_targets.csv")
        return True
    elif len(sys.argv) == 2 and sys.argv[1] != '--manual':
        logger.error("The wrong sys.arg has been provided. Please provide either no sys.args, or '--manual'.")
        sys.exit(1)
    elif len(sys.argv) > 2:
        logger.error("Too many sys.args have been provided. This script accepts either no sys.args, or '--manual'.")
        sys.exit(1)
    else:
        logger.error("Unspecified issue with sys.args. Please provide either no sys.args, or '--manual'.")
        sys.exit(1)


# -----------
# MANUAL PATH
# -----------

def readManualTargetList():
    """Reads external target list file to build list of reprovision targets for a manual run."""

    logger.info("Reading manual_reprovision_targets.csv to build list of reprovision targets.")
    try:
        with open('manual_reprovision_targets.csv', 'r') as target_list:
            csv_reader = csv.reader(target_list, delimiter=',')
            for row in csv_reader:
                reprovision_targets.append(row[0])
    except Exception as e:
        logger.error(f"Error, likely because no manual_reprovision_targets.csv was found. Exception object = {e}")


def clearManualTargetList():
    """Clears the external target list"""

    logger.info("Clearing manual_reprovision_targets.csv")
    try:
        with open('manual_reprovision_targets.csv', 'w'):
            pass
        logger.info("manual_reprovision_targets.csv has been cleared.")
    except Exception as e:
        logger.error(f"Error clearing manual_reprovision_targets.csv. Exception object = {e}")


# --------------
# REPROVISIONING
# --------------

def startReprovisionLoop(customers, NPVR_bundle_data):
    """
    Begins looping through all customers and calling necessary functions to reprovision each.

    Args:
        customers | An xml.dom nodelist where each node represents a customer from the XML file.
        NPVR_bundle_data | A list of tuples reflecting the intended NPVR provisioning (in minutes) for each bundle. 
    """

    logger.info("Looping through all targets to make a reprovision attempt for each.")
    for customer in customers:
        handleReprovision(customer, NPVR_bundle_data)


def handleReprovision(customer, NPVR_bundle_data):
    """
    For a given customer, calls the functions to get the proper data for a put request, and the function to make the put request.
    
    Args:
        customer | an xml.dom node representing a customer. 
        NPVR_bundle_data | A list of tuples reflecting the intended NPVR provisioning (in minutes) for each bundle. 
    """

    customer_id = customer.getAttribute("id")
    fileQuota, specifiedQuota = getIntendedNPVR(customer, NPVR_bundle_data)
    for target_id in reprovision_targets:
        if target_id == customer_id:
            customer_data = getDataForReprovision(customer_id)
            if customer_data is not None:
                reprovisionCustomer(customer_id, customer_data, specifiedQuota)


def getDataForReprovision(customer_id):
    """
    Makes a Get request to Prodis to fetch the 'CustomerData' field for the subsequent Put request.
    
    Args:
        customer_id | An integer representing the id of a specific customer. 
    
    Returns:
        customer_data | A string corresponding to a customer. Required for making a put request for that customer.
    """

    url = f"{prodisURL}/{customer_id}"
    response = requests.get(url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        namespaces = {'ns': 'urn:eventis:crm:2.0'}
        customer_data = root.find('ns:CustomerData', namespaces).text
        logger.info(f"Get request to prodis for customer {customer_id} successful.")
        return customer_data
    else:
        logger.error(f"Get request to Prodis for customer {customer_id} failed.")
        return None


def reprovisionCustomer(customer_id, customer_data, new_npvr_quota):
    """
    Makes a Put request to Prodis to reprovision the customer.
    
    Args:
        customer_id | An integer representing the id of a specific customer.
        customer_data | A string corresponding to a customer. Required for making a put request for that customer.
        new_npvr_quota | Integer, representing how many minutes a customer should be provisioned for NPVR. 
    """

    xml_data = f'''<?xml version="1.0" encoding="utf-8"?>
    <Customer id="{customer_id}" xmlns="urn:eventis:crm:2.0" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <NPVRQuota>{new_npvr_quota}</NPVRQuota>
        <CustomerData>{customer_data}</CustomerData>
    </Customer>'''
    url = f"{prodisURL}/{customer_id}"
    headers = {'Content-Type': 'application/xml'}
    response = requests.put(url, data=xml_data, headers=headers)
    if response.status_code == 200:
        logger.info(f"Attempt to reprovision customer {customer_id} succeeded.")
    else:
        logger.info(f"Attempt to reprovision customer {customer_id} returned status code {response.status_code}.")


# -----------------------
# FIRST MAIN CONTINUATION
# -----------------------

def findMismatches(customers, NPVR_bundle_data):
    """
    Searches for mismatches between actual and intended NPVR provisioning for each customer to build list of reprovision targets.
    
    Args:
        customers | An xml.dom nodelist where each node represents a customer from the XML file.
        NPVR_bundle_data | A list of tuples reflecting the intended NPVR provisioning (in minutes) for each bundle.

    Modifies:
        reprovision_targets | List containing customer IDs of customers which will be reprovisioned. 
    """

    logger.info("Checking all customers for mismatches to build list of reprovision targets.")
    for customer in customers:
        customer_id = customer.getAttribute("id")
        fileQuota, specifiedQuota = getIntendedNPVR(customer, NPVR_bundle_data)
        if fileQuota != specifiedQuota:
            reprovision_targets.append(customer_id)


def getIntendedNPVR(customer, NPVR_bundle_data):
    """
    Determines how many minutes of NPVR a given customer has, and how many they should have.
    
    Args:
        customer | an xml.dom node representing a customer.
        NPVR_bundle_data | A list of tuples reflecting the intended NPVR provisioning (in minutes) for each bundle.
    
    Returns:
        fileQuota | Integer representing how many minutes of NPVR the customer currently has provisioned.
        specifiedQuota | Integer representing how many minutes of NPVR the customer is supposed to have provisioned.
    """

    if NPVR_bundle_data == []:
        logger.error("NPVR_bundle_data list is empty. Aborting script.")
        sys.exit(1)
    elif NPVR_bundle_data == None:
        logger.error("NPVR_bundle_data list is missing. Aborting script.")
        sys.exit(1)     
    else:
        try:
            npvr_quota = customer.getElementsByTagName("NPVRQuota")
            if npvr_quota.length > 0:
                fileQuota = int(customer.getElementsByTagName("NPVRQuota")[0].firstChild.data)
            else:
                fileQuota = 0
            subscriptions = customer.getElementsByTagName("SubscriptionProduct")
            specifiedQuota = 0
            for subscriptionProduct in subscriptions:
                subscription_id = int(subscriptionProduct.getAttribute("id"))
                for line in NPVR_bundle_data:
                    bundle_id = int(line[0])
                    bundle_npvr = int(line[1])
                    if bundle_id == subscription_id:
                        if specifiedQuota < bundle_npvr:
                            specifiedQuota = bundle_npvr
            return fileQuota, specifiedQuota
        except Exception as e:
            logger.error(f"An error occured while getting NPVR data for customer {customer.getAttribute('id')}. Exception object = {e}")


# ----------
# ABORT PATH
# ----------

def logMismatchedCustomers(mismatchCount):
    """
    Logs all mismatched customers.
    
    Args:
        mismatchCount | Integer representing length of list reprovision_targets, and thus how many customers have been found with a mismatch between actual and intended NPVR provisioning.
    """

    logger.info("Logging all customers with a mismatch.")
    for customer_id in reprovision_targets:
        logger.info(f"Mismatch detected for customer {customer_id}.")
    logger.info(f"Number of customers with NPVR mismatch = {mismatchCount}.")


def writeManualTargetList():
    """Writes the list of customer ids to an external file which acts as the input for a manual script run."""

    logger.info("Writing list of reprovision targets to manual_reprovision_targets.csv.")
    try:
        with open('manual_reprovision_targets.csv', 'w') as target_list:
            writer = csv.writer(target_list, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            for customer in reprovision_targets:
                writer.writerow([str(customer)])
        logger.info("manual_reprovision_targets.csv is ready for a manual script run.")
    except Exception as e:
        logger.error(f"Issue with creating or writing to file. Exception object = {e}")


def createNewTicket(mismatchCount):
    """
    Creates a JIRA ticket to alert someone to the high number of mismatches.
    
    Args:
        mismatchCount | Integer representing length of list reprovision_targets, and thus how many customers have been found with a mismatch between actual and intended NPVR provisioning.
    """

    logger.info("Creating and assigning a JIRA ticket.")
    jsonBody = {
        "fields": {
            "project":
                {
                    "key": "DIV"
                },
            "summary": "KROKET - Quota: " + str(mismatchCount) + " NPVR mismatches",
             "description": '''KROKET QUOTA ALERT. \n This is an automatically generated ticket. \n
                            This script checks active customers for wrong provisioning of NPVR, and reprovisions customers with a mismatch. This ticket has been created because the number of customers who need to be reprovisioned is too high. \n
                            Please check the logs at DivitelQL Toolserver /home/divitel/ql_kroket/quota. If you believe there is a problem, please look into it. Otherwise, all customers can be reprovisioned by running the script with the '--manual' argument.''',
            "labels": ["KROKET_QUOTA"],
            "issuetype": {"name": "Incident"},
            "customfield_11114": [{"key": "QLV-59"}],
            "customfield_11211": {"value": "<img src=\"/images/icons/priorities/minor.png\"/>Prio 4"}
        }
    }
    response = requests.post(url=pendenzenURL + "/issue",
                             json=jsonBody, auth=auth)
    if response.status_code == 201:
        responseTicket = json.loads(response.text)
        assignTicket(responseTicket["self"])
        issue_key = responseTicket.get('key', 'Unknown')
        web_url = f"https://<REDACTED>/{issue_key}"
        logger.info(f"New ticket created at {web_url}")
    else:
        logger.error("Failed to create a new ticket.")


def assignTicket(url):
    """
    Assigns the new ticket to Divitel Support.
    
    Args:
        url | string which represents the URL of the new ticket which has been created.
    """

    assignee = {
        "name": "dsupport"
    }
    response = requests.put(url=url + "/assignee",
                            json=assignee, auth=auth)
    if response.status_code == 204:
        logger.info("Ticket successfully assigned.")
    else:
        logger.error("Failed to assign ticket.")



if __name__ == '__main__':
    main()
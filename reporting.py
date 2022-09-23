import csv
import os 
import datetime
import logging
import json
import requests

###########################################################################
# Written by Fabian Ihle, fabi@ihlecloud.de                               #
# Created: 23.09.2022                                                     #
# github: https://github.com/n1tr0-5urf3r/openvas-confluence-reporting    #
#                                                                         #
# This script searches for new reports in csv format and uploads them to  #
# a confluence instance                                                   #
# ----------------------------------------------------------------------- #
# Changelog:                                                              #
# 230922 Version 1.0 - Initial release                                    #
###########################################################################


# CONFIGURE THOSE VALUES
# Use absolute value for path to prevent issues when running from crontab
REPORTS_PATH = "/absolute/path/to/the/folder/reports/"
ACCESS_TOKEN = "FILL-IN"
KEY_SPACE = "FILL-IN"
PAGE_IDS = {"Task Name": "page_id"}
API_URL = "FILL-IN"   # i.e. "https://confluence.domain.com/confluence/rest/api/content/"

HEADERS = {'Authorization': f"Bearer {ACCESS_TOKEN}", 'Content-Type': 'application/json'}

logging.basicConfig(level=logging.DEBUG)

def get_files():
    """
    This function returns a list of all csv files located in the REPORTS_PATH directory
    """
    return list(filter(lambda x: x.endswith('.csv'), os.listdir(REPORTS_PATH)))

def parse_file(file_path):
    """
    This function parses a given .csv report file and creates the report object from it.
    :params file_path: 

    :returns: the report dict object
    """
    report_csv = []
    report = {}

    with open(f"{REPORTS_PATH}{file_path}", mode = 'r') as f:
        csv_file = csv.reader(f)
        report["date"] = str(datetime.datetime.now())[:10]

        for line in csv_file:
            name = line[13]
            try:
                if float(line[4]) >= 7.:
                    entry = [line[0], line[1], line[2], line[3], line[4], line[7], line[8], line[11], line[18]]
                    report_csv.append(entry)
            except ValueError:
                # Skip severity filter for header line
                entry = [line[0], line[1], line[2], line[3], line[4], line[7], line[8], line[11], line[18]]
                report_csv.append(entry)
                continue
        report["csv"] = report_csv
        report["name"] = name
    if len(report['csv']) < 2:
        return None
    return report

def csv_to_html(report):
    """This function adds the html table value of the csv report to the report object

    :param report: dict object of the report
    :returns: None
    """
    ls = report["csv"]

    if len(ls) == 1:
        report["html"] = "<p>No critical vulnerabilities with CVSS > 7.0 found.</p>"
        return

    s = "<table><tr>"
    s += "".join([f"<th>{x}</th>" for x in ls[0]]) + "</tr>"
    for line in ls[1:]:
        s += "<tr>"
        for i, e in enumerate(line):
            e = e.replace("<", "&#060;")
            e = e.replace(">", "&#062")
            if i == 4:
                s += f"<td style='background-color:red;'>{e}</td>"
            else: 
                s += f"<td>{e}</td>"
        s += "</tr>"
        #s += "".join([f"<td>{x}</td>" for x in line]) + "</tr>"
    s += "</table>"
    report["html"] = s

def send_to_confluence(report):
    """
    This function takes the html values from the report object and sends it to your confluence instance to create a new page.

    :params report: The report object, being populated with the 'html' field
    """

    page_id = PAGE_IDS[report["name"]]
    title = f"{report['date']} {report['name']} openVAS Report"

    body = {
            "type": "page",
            "title": title,
            "ancestors": [
                {
                "id": page_id
                }
            ],
            "space": {
                "key": KEY_SPACE
            },
            "body": {
                "storage": {
                "value": report["html"],
                "representation": "storage"
                }
            } 
            }
    response = requests.post(API_URL, data=json.dumps(body), headers=HEADERS, verify=False)

    if response.status_code != 200:
        logging.error(f"Could not upload report of {report['name']} to confluence!: {response.status_code}")
        return False
    logging.info(f"Uploaded {report['name']}")
    return True

def archive_file(file):
    """
    Moves a file into the archive directory

    :params file: The file path as a string
    """
    os.rename(f"{REPORTS_PATH}/{file}", f"{REPORTS_PATH}/archive/{report['name']}_{report['date']}_report.csv")



if __name__ == "__main__":
    file_list = get_files()
    if not file_list:
        logging.info("Exiting, no new files")

    for file in file_list:
        try:
            report = parse_file(file)

            if report:
                csv_to_html(report)
                res = send_to_confluence(report)
                if res:
                    archive_file(file)
            else:
                logging.warn(f"File {file} was empty, will delete!")
                os.remove(f"{REPORTS_PATH}/{file}")

        except Exception as e:
            logging.error(f"Something went wrong while parsing the file {file}!")
            logging.error(str(e))
            continue

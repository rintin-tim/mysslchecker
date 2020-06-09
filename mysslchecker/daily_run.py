import sys
from google_sheet import GoogleSheet
import subprocess
import datetime
import traceback
import ssl_checker
import time
import os
from urllib.request import urlopen


def prod_server():
    """ after 30 mins of inactivity, heroku sleeps the Worker process required to run background processes - this
    prods the server to wake it up """

    checker_domain = os.getenv("CHECKER_DOMAIN", "http://0.0.0.0:5000")
    try:
        print("ping ssl checker to start worker. Domain is: {}".format(checker_domain))
        request = urlopen(checker_domain)
        print("ping result: ", request.msg)
    except Exception as err:
        print("**** ERROR pinging the SSL Checker website at {0}: Error: {1}".format(checker_domain, err))


def daily_run(mgmt_sheet_id, mgmt_tab_name="Users"):

    dailyRun = GoogleSheet(mgmt_sheet_id)

    users = dailyRun.get_values(mgmt_tab_name)

    if users:
        # if less than 4 items per row, add in spaces at the end
        for row in users:
            if len(row) < 6:
                for number in range(6 - len(row)):
                    row.append("")

        print("@@@@ let's run it @@@@")

        for i, user in enumerate(users):
            try:
                prod_server()  # prod the heroku server to wake up
                sheet_id = user[0]
                print("** daily run: sheet_id: {0} **".format(sheet_id))
                print("user: {}".format(i))
                row_dashboard_tab = user[1] if user[1] else None
                row_email_tab = user[2] if user[2] else None
                row_website_tab = user[3] if user[3] else None
                row_forgive = user[4] if user[4] else False
                if row_forgive:
                    if row_forgive == "TRUE":  # convert Google sheet boolean to Python boolean
                        row_forgive = True
                    else:
                        row_forgive = False

                if row_dashboard_tab:
                    dashboard_tab = row_dashboard_tab
                if row_email_tab:
                    email_tab = row_email_tab
                if row_website_tab:
                    website_tab = row_website_tab

                print("starting: ", sheet_id, " ", mgmt_sheet_id)
                ssl_checker.ssl_checker(sheet_id, dashboard_tab=dashboard_tab, email_tab=email_tab, domains_tab=website_tab,
                                        mgmt_sheet_id=mgmt_sheet_id, mgmt_tab_name=mgmt_tab_name, timeout=10, forgiving=row_forgive)

                time.sleep(10)
                print("finished: ", sheet_id, " ", mgmt_sheet_id)
            except Exception as e:
                print("error: {0}".format(e))
                continue

    else:
        print("no users in management sheet")


if __name__ == "__main__":
    mgmt_sheet_id = sys.argv[1]
    users_tab_name = sys.argv[2]

    print("start daily run")
    daily_run(mgmt_sheet_id, users_tab_name)


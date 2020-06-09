import subprocess
from email_ssl_alert import SendEmail
import re
from googleapiclient.errors import HttpError
import conversions
import time
import queue
import json
from rq import Queue
from worker import conn
import threading


class RunSSL:

    def __init__(self, domain_list, forgiving, timeout, mySheet, manage_sheet_object, recipients, start_time):
        self.domain_list = domain_list
        self.sorted_site_list = None
        self.mySheet = mySheet
        self.manage_sheet_object = manage_sheet_object
        self.recipients = recipients
        self.forgiving = forgiving
        self.timeout = timeout
        self.email_thread_list = None
        self.thread_max = 30
        self.start_time = start_time

    def elapsed_time(self):
        return time.time() - self.start_time

    def run_site_results(self, domain_list=None, forgiving=None, timeout=None):
        domain_list = self.domain_list if not domain_list else domain_list
        forgiving = self.forgiving if not forgiving else forgiving
        timeout = self.timeout if not timeout else timeout

        print("in the function")
        site_list = []  # list of site objects

        def run_ssl_cert(site_queue: queue.Queue):
            """ calls the ssl_cert script and returns the result for each domain """

            arg_string = "--all "
            if forgiving:
                arg_string += "--forgiving "
            if timeout:
                arg_string += "--timeout {0}".format(timeout)

            while not site_queue.empty():

                site_row = site_queue.get()

                url = site_row[0]  # return the first cell per row
                if url.startswith(("https://", "http://")):
                    url = url[url.find("//")+2:]  # urls cannot be regex'ed so need to remove protocol from string

                domain_pattern = r"(?i)\b([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}\b"
                domain = re.match(domain_pattern, url)  # return only the domain (strip the protocol or any sub '/' pages)

                if domain:
                    url = domain.group(0)  # return the matched string

                    # create ssl script for a site
                    port = None
                    if site_row[1]:
                        port = site_row[1]  # if there's a second value, pass it in as the port
                        script = "python3 ssl_cert.py {0} -p {1} {2}".format(url, port, arg_string)
                    else:
                        # print("python3 ssl_cert.py {0} {1}".format(url, arg_string))
                        script = "python3 ssl_cert.py {0} {1}".format(url, arg_string)

                    request = subprocess.Popen(script, stdout=subprocess.PIPE, universal_newlines=True,
                                               shell=True)  # run script

                    if request is None:
                        print("script request '{0}' didn't return an output".format(script))
                        return

                    script_result, script_error = request.communicate()  # get result of script as a string. ignore errors

                    # site = dict(literal_eval(script_result))  # convert string to dictionary
                    site = json.loads(script_result)  # convert string to dictionary

                    if port and (not port == 443):
                        site["url"] = "http://{0}:{1}".format(url, port)  # add url to site object
                        print(site["url"])
                    else:
                        site["url"] = "https://{0}".format(url)
                        print(site["url"])

                    # internal_site_list.append(site)
                    site_list.append(site)
                    # progress.increase()

                else:
                    print("'{0}' is not a valid domain - ignored".format(url))

                site_queue.task_done()
            return

        q = queue.Queue()

        for domain in domain_list:
            q.put(domain)

        thread_list = []

        thread_no = 1
        if 1 <= len(domain_list) <= self.thread_max:
            thread_no = len(domain_list)
        elif self.thread_max <= len(domain_list):
            thread_no = self.thread_max

        for i in range(thread_no):
            t = threading.Thread(target=run_ssl_cert, args=(q,), name="thread {}".format(i))
            thread_list.append(t)
            t.setDaemon(True)
            t.start()
            # print("thread started: ", t.name)

        for t in thread_list:
            t.join()

        q.join()

        print("elapsed time for run_site_results (queue) completion: ", self.elapsed_time())

        if len(site_list) == 0:
            message = self.mySheet.no_values_message(self.mySheet.domains_tab_name)
            print(message)
            return 1, message
        else:
            self.sorted_site_list = conversions.get_sorted_categories(site_list)
            return 0, self.sorted_site_list

    def run_dashboard_update(self, sorted_site_list=None, mySheet=None, forgiving=None):
        sorted_site_list = self.sorted_site_list if not sorted_site_list else sorted_site_list
        # print(sorted_site_list)
        mySheet = self.mySheet if not mySheet else mySheet
        forgiving = self.forgiving if not forgiving else forgiving

        # Write to Google Sheet
        values_list = []  # list of values to be written to the google sheet

        # print("sort values to be written start:", time.time() - st)
        for cat in sorted_site_list:
            if sorted_site_list[cat]:  # if category isn't empty (i.e. if there are sites in the category)
                for site in sorted_site_list[cat]:  # for each site in the category
                    if site["ssl_status"] == "pass":
                        to_write = []
                        for key in mySheet.site_keys:  # values written in same order as GoogleSheets.site_keys()
                            if key not in site:
                                to_write.append("None")
                            else:
                                to_write.append(site[key])
                        values_list.append(to_write)  # add this tuple to List to be written to the sheet
                    else:
                        if site["ssl_status"] == "missing":
                            message = "** SSL certificate not found **"  # an error with no SSL date means there's no SSL
                        elif site["ssl_status"] == "fail":
                            message = "** Invalid SSL **"  # an error WITH an SSL date means there's some other SSL issue

                        to_write_error = []
                        for key in mySheet.site_keys:  # values written in same order as GoogleSheets.site_keys()
                            if key == "url":
                                to_write_error.append(site[key])
                            elif key == "countdown":
                                to_write_error.append(message)
                            elif key == "error":
                                to_write_error.append(site[key])
                            elif key in site:
                                to_write_error.append(site[key])
                            else:
                                to_write_error.append("")
                        values_list.append(to_write_error)  # add this tuple to List to be written to the sheet

        # print("sort values to be written end:", time.time() - st)

        # convert the expiry and start times into the google sheet format
        expiry_index = list(mySheet.dashboard_mapping.keys()).index("expiry")  # get index position based from position in the heading
        start_index = list(mySheet.dashboard_mapping.keys()).index("start")  # get position of start key based on the headings
        for site in values_list:
            if site[expiry_index]:
                site[expiry_index] = mySheet.google_time(site[expiry_index])  # replace item at list index with google time
            if site[start_index]:
                site[start_index] = mySheet.google_time(site[start_index])

        # print("update dashboard start:", time.time() - st)
        # Update Dashboard with retrieved site data.
        try:
            mySheet.forgive = forgiving  # set the forgiveness mode so that the update link in the google sheet is correct
            timestamp = mySheet.update_dashboard(values_list)
            mySheet.format_dashboard(sorted_site_list)
            print("elapsed time for run_dashboard_update completion: ", self.elapsed_time())
            return 0, timestamp  # 0 = success
            # return timestamp

        except HttpError as err:
            error = str(err.content)
            if "The caller does not have permission" in error:  # if no write permission
                message = "SSL Checker has not been given edit access to the Google Sheet. Google sheet: {0}. User: {1}".format(mySheet.spreadsheet_id, mySheet.credentials._service_account_email)
                print(message)
                return 1, message, error  # 1 = failure
            else:
                message = "Unable to create/update/access the required spreadsheet {0}. Error: {1}".format(mySheet.spreadsheet_id, error)
                print(message)
                return 1, message, error

        # print("update dashboard end:", time.time() - st)

    def run_management_sheet_setup(self, manage_sheet_object=None, dashboard_tab=None, email_tab=None, domains_tab=None, forgiving=None):

        # print("management sheet activities start:", time.time() - st)
        mgmtSheetObj = self.manage_sheet_object if not manage_sheet_object else manage_sheet_object

        dashboard_tab = self.mySheet.dashboard_tab_name if not dashboard_tab else dashboard_tab
        email_tab = self.mySheet.email_tab_name if not email_tab else email_tab
        domains_tab = self.mySheet.domains_tab_name if not domains_tab else domains_tab
        forgiving = self.forgiving if not forgiving else forgiving

        # create user/mgmt object - access object via sheet id
        this_usr_obj = mgmtSheetObj.create_user(dashboard_tab, email_tab, domains_tab, forgiving)

        users_dict = mgmtSheetObj.update_management_users(this_usr_obj)
        user_value_list = mgmtSheetObj.user_dict_to_list(users_dict) if users_dict else None

        # write user dict back to sheet (clear old values first)
        # print("update the management sheet:", time.time() - st)
        try:
            mgmtSheetObj.update_management_sheet(user_value_list)
            print("elapsed time for run_management_sheet completion: ", self.elapsed_time())
            return 0,
        except HttpError as err:
            error = str(err.content)
            message = "An error occured when trying to store details for this sheet for future updates. Your sheet has been updated but you will not receive regular email updates - sorry about that"
            # mgmt_sheet_error = message
            return 1, message, error

    def run_email_delivery(self, sorted_site_list=None, mySheet=None, recipients=None):

        sorted_site_list = self.sorted_site_list if not sorted_site_list else sorted_site_list
        mySheet = self.mySheet if not mySheet else mySheet
        recipients = self.recipients if not recipients else recipients
        self.recipients = recipients  # set recipients if not set
        dashboard_link = mySheet.dashboard_url
        refresh_link = mySheet.get_refresh_link()
        spreadsheet_title = mySheet.get_spreadsheet_title()

        # Create the SendEmail object. Stores sheetIds, tab names, etc
        emailObj = SendEmail(sorted_site_list, dashboard_link, spreadsheet_title, refresh_link)

        def send_email(email_queue: queue.Queue):
            while not email_queue.empty():
                contact_i, contact = email_queue.get()
                email_pattern = r"(?i)[^@]+@[^@]+\.[^@]+"  # has exactly one '@' sign, and at least one '.' in the part after the '@'
                if (contact["email"] == mySheet.email_mapping["email"]["default"]):  # default email value which hasn't been changed
                    pass
                    # print("skipping over default email value")
                elif re.match(email_pattern, contact["email"]):
                    # check if an email should be sent to the contact
                    updated_contact = emailObj.send_email(contact)
                    recipients[contact_i] = updated_contact  # update recipient (i.e. contact object) with result
                else:
                    print("A problem occurred with an email contact and it was not processed. The contact is: {0} ".format(
                        contact))
                email_queue.task_done()

            return

        # print("process emails end:", time.time() - st)

        print("recipients: {0}".format(recipients))

        if not recipients:
            message = mySheet.no_values_message(mySheet.email_tab_name)
            print(message)
            return 1, message

        email_q = queue.Queue()

        for e_index, e_email in enumerate(recipients):  # the index of each recipient is used to update the send date
            email_q.put((e_index, e_email))

        if email_q.qsize() < self.thread_max:
            email_thread_no = email_q.qsize()
        else:
            email_thread_no = self.thread_max

        print("email threading start")
        email_thread_list = []
        for thread in range(email_thread_no):
            email_t = threading.Thread(target=send_email, args=(email_q,), daemon=True)
            email_t.start()
            email_thread_list.append(email_t)
            # print("email thread started with name: {}".format(email_t.name))

        print("email threading to init")
        # self.email_thread_list = email_thread_list

        for email_t in email_thread_list:
            email_t.join()
            # del email_t

        print("elapsed time for run_email_delivery completion: ", self.elapsed_time())
        return 0,
        # return email_thread_list  # remove return? not joining thread

    def run_tidy_email(self, recipients=None):
        print("get recipients")
        recipients = self.recipients if not recipients else recipients
        print("update email tab")
        self.mySheet.update_email_tab(recipients)
        print("elapsed time for run_tidy_email completion: ", self.elapsed_time())

    def background_from(self, position):
        """ runs the rest of an execution from the given position """
        if position == "sites":
            self.run_site_results()
            self.run_dashboard_update()
            self.run_management_sheet_setup()
            self.run_email_delivery()
            self.run_tidy_email()
        elif position == "dashboard":
            self.run_dashboard_update()
            self.run_management_sheet_setup()
            self.run_email_delivery()
            self.run_tidy_email()
        elif position == "management":
            self.run_management_sheet_setup()
            self.run_email_delivery()
            self.run_tidy_email()
        elif position == "email":
            self.run_email_delivery()
            self.run_tidy_email()
        elif position == "tidy":
            print("do an update")
            self.run_tidy_email()

    def send_to_redis(self, position):
        try:
            q = Queue(connection=conn)
            result = q.enqueue(self.background_from, position,)
            print("sent to redis from position: {0}. Job ID: {1}. Redis key: {2}".format(position, result.id, result.key.decode("utf-8")))
            return 0, result
        except Exception as err:
            print("redis connection error: ", str(err))
            message = "An error occurred when trying to complete this task..."
            return 1, message, str(err)

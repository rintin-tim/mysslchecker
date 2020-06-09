from google_sheet import GoogleSheet
import subprocess
# from ast import literal_eval
import conversions
# from email_ssl_alert import SendEmail
import re
import sys
import getopt
from flask import Flask, send_from_directory, Response
from flask import request as frequest
from googleapiclient.errors import HttpError
import datetime
import conversions
from web_messages import WebMessages
import os
from flask import render_template
import time
import threading
# import numpy
import queue
import json
from management_sheet import ManagementSheet
# import multiprocessing
from rq import Queue
from worker import conn
import func_ssl_checker
from func_ssl_checker import RunSSL
import math



app = Flask(__name__)

@app.route('/streams')
# TODO would need to run in an iframe in a separate thread?
def stream():

    print("in the stream")

    def eventStream():
        count = 0
        while count < 10:
            time.sleep(1)
            # wait for source data to be available, then push it
            count += 1
            print(count)
            yield 'data: {}\n\n'.format(count)

    return Response(eventStream(), mimetype="text/event-stream")

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    # app.run(host='0.0.0.0', port=port)  # comment for local. TODO detect when running locally somehow

    try:
        print("starting flask server")
        app.run(debug=True, host='0.0.0.0', port=port)  # comment for local.
        # app.run(debug=True)  # uncomment for local.
        # app.run(threaded=True)

    except OSError:
        print("flask server already running")
        app.run(debug=True, host='0.0.0.0', port=port)  # comment for local.  TODO does this line make sense?


@app.route('/')
def index():
    # return "<h1>Hi Tim</h1>"
    return render_template("form.html")


@app.route('/development')
def development():
    # return "<h1>Hi Tim</h1>"
    return render_template("form.html")


@app.route('/sheet-update')
def update_tab():
    # return "<h1>Hi Tim</h1>"
    return render_template("form.html")


@app.route('/form', methods=['POST'])
def form_ssl_checker():

    # TODO remove the GET completely

    if frequest.method == 'GET':
        print("get request ignored")
        return "i'm alive"

    elif frequest.method == 'POST':
        # sheet_id = sheetid.strip("/")

        # TODO Fix API error when doing multiple daily runs (add timeout?)

        sheet_url = frequest.form.get("sheeturl")
        dashboard_tab = "Dashboard" if not frequest.form.get("dashboardname") else frequest.form.get("dashboardname")
        email_tab = "Emails" if not frequest.form.get("emailname") else frequest.form.get("emailname")
        domains_tab = "Websites" if not frequest.form.get("domains") else frequest.form.get("domains")

        email_address = frequest.form.get("emailaddress")
        email_priority = frequest.form.get("emailpriority")
        email_frequency = frequest.form.get("emailfrequency")
        form_site_list = frequest.form.get("websitelist")

        email_address2 = frequest.form.get("emailaddress2")
        email_priority2 = frequest.form.get("emailpriority2")
        email_frequency2 = frequest.form.get("emailfrequency2")

        email_address3 = frequest.form.get("emailaddress3")
        email_priority3 = frequest.form.get("emailpriority3")
        email_frequency3 = frequest.form.get("emailfrequency3")

        form_forgive = False if not frequest.form.get("forgive") else True
        form_timeout = 2 if not frequest.form.get("timeout") else frequest.form.get("timeout")

        management_sheet_id = None if not frequest.form.get("management_sheet_id") else frequest.form.get("management_sheet_id")

        def get_sheet_id(sheet_url):
            id_match = re.search(r"(?<=spreadsheets/d/).*?($|(?=[$\?#=/]))", sheet_url)  # all characters between d/ and end of string OR tp the first / or other break
            if id_match:
                sheet_id = id_match[0]
            else:
                sheet_id = sheet_url
            return sheet_id

        def clean_web_list(form_websites):
            """ splits on whitespace character or comma, then removes any left over white space items from the list"""
            form_websites = re.split(r"\s+|,(\s)+|,", form_websites)
            cleaned = []
            for item in form_websites:
                if item and re.match(r"\S", item):  # ensures string starts with a non-whitespace character
                    cleaned.append(item)
            return cleaned

        sheet_id = get_sheet_id(sheet_url)
        # split out the websites provided in the form
        if form_site_list:
            form_site_list = clean_web_list(form_site_list)
            # form_site_list = re.split(r"\s+|,(\s)+|,", form_site_list)

        email_obj = {
            "email": email_address,
            "priority": email_priority,
            "frequency": email_frequency
        }

        email_list = []

        if email_address:
            email = {}
            email["email"] = email_address
            email["priority"] = email_priority
            email["frequency"] = email_frequency
            email_list.append(email)

        if email_address2:
            email = {}
            email["email"] = email_address2
            email["priority"] = email_priority2
            email["frequency"] = email_frequency2
            email_list.append(email)

        if email_address3:
            email = {}
            email["email"] = email_address3
            email["priority"] = email_priority3
            email["frequency"] = email_frequency3
            email_list.append(email)

        result_html = ssl_checker(sheet_id, dashboard_tab=dashboard_tab, email_tab=email_tab, domains_tab=domains_tab,
                                  web=True, form_sites=form_site_list, form_email_list=email_list,
                                  forgiving=form_forgive, timeout=form_timeout, mgmt_sheet_id=management_sheet_id)

        dt_now = conversions.insert_date_now()
        date_stamp = "<br><p>Time Now: {0}</p>".format(dt_now)

        # return result_html + date_stamp
        return render_template("results.html", result_html=result_html, date_stamp=date_stamp)


def ssl_checker(sheet_id, dashboard_tab=None, email_tab=None, domains_tab=None, web=True, form_sites=None,
                 mgmt_sheet_id=None, mgmt_tab_name=None, form_email_list=None, forgiving=False, timeout=5,update_tab=None):

    st = time.time()
    print('start time: ', st)

    if not dashboard_tab:
        dashboard_tab = "Dashboard"
    if not email_tab:
        email_tab= "Emails"
    if not domains_tab:
        domains_tab = "Websites"
    if not mgmt_sheet_id:
        mgmt_sheet_id = "1cpCZTkLwaBFk1ZfLlxzJrs60PAsMqA5zLf2DJ3jFJ60"
    if not mgmt_tab_name:
        mgmt_tab_name = "Users"
    if not update_tab:
        update_tab = "Update Sheet"
    # if not form_email:
    #     form_email = None  # None required rather than ""?

    mgmtSheetObj = ManagementSheet(mgmt_sheet_id, mgmt_tab_name, sheet_id)
    mySheet = GoogleSheet(sheet_id, forgiving=forgiving)
    web_msg = WebMessages(mySheet)

    # create tabs
    try:
        mySheet.create_default_tabs(dashboard_tab, email_tab, domains_tab,
                                    form_sites=form_sites, form_email_list=form_email_list, update=update_tab)
    except HttpError as err:
        error = str(err.content)
        # formatted_err = error.replace(r"\n", "<br>")
        if "The caller does not have permission" in error:
            message = "SSL Checker has not been given permission to the Google Sheet. To use SSL Checker, please give 'Edit' permission to: {1}".format(sheet_id, mySheet.credentials._service_account_email)
            if web:
                return web_msg.general_err_msg(message)
            else:
                print(message)
        elif "Requested entity was not found" in error:
            message = "SSL Checker could not find the Google Sheet you provided. Google sheet: {0}.".format(sheet_id)
            if web:
                return web_msg.general_err_msg(message)
            else:
                print(message)
        else:
            message = "Unable to create or access the required spreadsheet {0}.".format(sheet_id)
            if web:
                return web_msg.msg_with_error(message, error)
            else:
                print(message + "error: ".format(error))
        sys.exit(1)

   # get the list of domains from Google Sheet
    domain_list = mySheet.get_domains()  # returns list of domains from specified domains tab

    if not domain_list:
        message = mySheet.no_values_message(mySheet.domains_tab_name)
        if web:
            return web_msg.general_err_msg(message)
        else:
            print(message + "\n sheet id: ".format(sheet_id))
        sys.exit(1)

    # get the list of email recipients
    recipients = mySheet.get_email_contacts()

    # create run object
    run = RunSSL(domain_list, forgiving, timeout, mySheet, mgmtSheetObj, recipients, st)

    # DECISION #1 - ASSESS QUEUE LENGTH
    # Switch to background task if queue could take longer than Heroku timeout
    elapsed_time = run.elapsed_time()
    print("sites decision time: ", elapsed_time)

    print("http timeout is: {}".format(timeout))
    max_queue_time = int(timeout)  # used to calculate queue time. initial value is timeout.

    threshold = 23 if not os.getenv("LOCALENV") else 255   # number of elapsed seconds before pushing to redis
    print("threshold is: ", threshold)

    if forgiving:
        max_queue_time = max_queue_time * 2  # double estimate if a redirect could be followed
    if len(domain_list) > run.thread_max:  # if we cannot start all threads at the same time
        max_queue_time = max_queue_time * math.ceil(len(domain_list) / run.thread_max)  # divide site qty by max threads and round up to next integer, then multiply by queue estimate
    max_queue_time = max_queue_time + elapsed_time
    print("max queue estimate is: ", max_queue_time)
    minutes_required = math.ceil(max_queue_time / 60)
    if max_queue_time > threshold:  # includea elapsed time taken - if the worse case scenario is greater than this number, go straight to redis
        print("#### run redis from sites (exceeds max queue time)")
        result = run.send_to_redis("sites")
        if result[0] == 0:
            return web_msg.redis_ssl_site_result_msg(minutes_required)
        else:
            return web_msg.msg_with_error(result[1], result[2])

    elapsed_time = run.elapsed_time()
    print("sites decision time: ", elapsed_time)
    # print("sites decision time: ", time_now - st)
    if elapsed_time > threshold:
        print("#### run redis from sites")
        result = run.send_to_redis("sites")
        if result[0] == 0:
            return web_msg.redis_ssl_site_result_msg(minutes_required)
        else:
            return web_msg.msg_with_error(result[1], result[2])
    else:
        # site_list = run.run_site_results()
        site_list_result = run.run_site_results()
        if site_list_result[0] == 1:
            return web_msg.general_err_msg(site_list_result[1])
        else:
            # rearrange sites into sorted categories (via conversions.get_sorted_categories())
            sorted_site_list = site_list_result[1]

    # DECISION #2 - DASHBOARD
    # run the dashboard update
    elapsed_time = run.elapsed_time()
    print("dashboard decision time: ", elapsed_time)
    if elapsed_time > (threshold + 2):
        print("#### run redis from dashboard")
        result = run.send_to_redis("dashboard")
        if result[0] == 0:
            return web_msg.redis_dashboard_updating_msg()
        else:
            return web_msg.msg_with_error(result[1], result[2])
    else:
        dashboard_result = run.run_dashboard_update(sorted_site_list)
        if dashboard_result[0] == 1:  # indicates an error
            return web_msg.msg_with_error(dashboard_result[1], dashboard_result[2])

    # DECISION #3 - MANAGEMENT SHEET UPDATE
    # Add/update the management sheet to ensure user sheet is updated in daily_run.py
    elapsed_time = run.elapsed_time()
    print("management decision time: ", elapsed_time)
    if elapsed_time > (threshold + 2):
        print("#### run redis from management")
        result = run.send_to_redis("management")
        if result[0] == 0:
            return web_msg.redis_dashboard_complete_msg()
        else:
            return web_msg.msg_with_error(result[1], result[2])
    else:
        management_result = run.run_management_sheet_setup()
        if management_result[0] == 1:
            return web_msg.msg_with_error(management_result[1], management_result[2])

    # DECISION #4 - SEND EMAILS
    # Send any emails due for delivery
    elapsed_time = run.elapsed_time()
    print("email decision time: ", elapsed_time)
    
    if elapsed_time > (threshold + 2):
        print("#### run redis from email")
        # send_to_redis = "dashboard"
        result = run.send_to_redis("email")
        if result[0] == 0:
            return web_msg.redis_dashboard_complete_msg()
        else:
            message = web_msg.redis_error_send_email()
            return web_msg.msg_with_error(message, result[2])
    else:
        email_result = run.run_email_delivery()
        if email_result[0] == 1:
            return web_msg.general_err_msg(email_result[1])

    # DECISION #5 - TIDY
    # Update the formatting on the email tab to include dropdowns for any email address
    elapsed_time = run.elapsed_time()
    print("email update decision time: ", elapsed_time)
    
    if elapsed_time > (threshold + 2):
        print("#### run redis from email update (tidy)")
        result = run.send_to_redis("tidy")
        if result[0] == 0:
            return web_msg.redis_tidy_msg()
        else:
            message = web_msg.redis_error_tidy()
            return web_msg.msg_with_error(message, result[2])
    else:
        run.run_tidy_email()

    print("update emails tab finish:", run.elapsed_time())

    # return page confirmation
    if web:
        print("completed in: ", run.elapsed_time())
        return web_msg.dashboard_success()

    sys.exit(0)


if __name__ == "__main__":
    print("running ssl checker.py")

# TODO rename app
# TODO update comments with explanations

# not now
# TODO merge heroku changes into pycharm folder
# TODO  consider a suite of testing variables determined by env variable
# TODO  look into better (longer) heroku logging

# TODO we could have one list for WWW and one for non WWW;s and one for PNPD
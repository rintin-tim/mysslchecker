from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from datetime import datetime

from collections import OrderedDict
import conversions
import pytz
from copy import deepcopy
import os

class GoogleSheet:


    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    SERVICE_ACCOUNT_FILE = 'mysslchecker-06626ad53533.json'

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE,
                                                                        scopes=SCOPES)  # handles authorisation request to authorisation server (and return of the access token) https://www.youtube.com/watch?v=CPbvxxslDTU

    service = build('sheets', 'v4', credentials=credentials)  # request service from resource server (with access token)

    checker_domain = os.getenv("CHECKER_DOMAIN", "http://0.0.0.0:5000")


    def __init__(self, spreadsheet_id, forgiving=False):
        self.spreadsheet_id = spreadsheet_id
        self.spreadsheet_name = None
        self.dashboard_tab_id = None
        self.dashboard_tab_name = None
        self.dashboard_url = None
        self.dashboard_header = self.get_mapping_list(self.dashboard_mapping, "header")
        self.site_keys = list(self.dashboard_mapping.keys())  # the keys for a site object. this returns the order that values will be returned in the dashboard, edit "header_mapping" to change this order
        self.email_tab_id = None
        self.email_tab_name = None
        self.email_header = self.get_mapping_list(self.email_mapping, "header")
        self.email_default_row = self.get_mapping_list(self.email_mapping, "default")
        self.domains_tab_id = None
        self.domains_tab_name = None
        self.domains_header = self.get_mapping_list(self.domain_mapping, "header")
        self.domains_default_row = self.get_mapping_list(self.domain_mapping, "default")
        self.update_sheet_id = None
        self.update_tab_name = None
        self.forgive = forgiving


    tab_notes = {
        "dashboard": "Welcome to SSL Checker! This is the main dashboard. The header colour matches your highest priority SSL certificate. To enter websites, go to the Websites tab.",
        "emails": "Multiple email addresses can be entered simply enter each email on a new row. To get started you can enter only an email address and default values will be used for the other columns. These can be changed later",
        "priority": "Determines how far in advance you are warned of an SSLs expiry",
        "frequency": "Determines how often you receive alerts within your chosen expiration window",
        "domains": "Enter the web address (domain) for each website on a new line.",
        "ports": "If the SSL Certificate is on a port other than 443, enter the number in this port column. If the SSL is on 443, this column can be left blank",
        "update": "If you add an email or address or website and would like to run SSL checker immediately, click the link below"
    }

    dashboard_mapping = OrderedDict([
        ("url", OrderedDict([("header", "URL"), ("width", "200"), ("notes", tab_notes["dashboard"])])),
        ("name", OrderedDict([("header", "Certificate Subject"), ("width", "250")])),
        ("countdown", OrderedDict([("header", "Time Left"), ("width", "250")])),
        ("expiry", OrderedDict([("header", "Expiry Date"), ("width", "170")])),
        ("start", OrderedDict([("header", "Start Date"), ("width", "150")])),
        ("number", OrderedDict([("header", "Serial Number"), ("width", "170")])),
        ("issuer", OrderedDict([("header", "Issuer Details"), ("width", "250")])),
        ("error", OrderedDict([("header", "Additional Info"), ("width", "180")])),
    ])

    email_mapping = OrderedDict([
        ("email", OrderedDict([("header", "Email Address"), ("default", "example@example.com"), ("changed", ""), ("width", "220"), ("notes", tab_notes["emails"])])),
        ("priority", OrderedDict([("header", "Expiration Window"), ("default", "3 months"), ("changed", ""), ("width", "170"), ("notes", tab_notes["priority"])])),
        ("frequency", OrderedDict([("header", "Frequency"), ("default", "Daily"), ("changed", ""), ("width", "120"), ("notes", tab_notes["frequency"])])),
        ("last", OrderedDict([("header", "Last Sent"), ("default", ""), ("changed", ""), ("width", "200")]))
    ])

    domain_mapping = OrderedDict([
        ("domains", OrderedDict([("header", "Enter Domains"), ("width", "225"), ("default", "expired.badssl.com"), ("notes", tab_notes["domains"])])),
        ("ports", OrderedDict([("header", "Port # (leave blank if 443)"), ("width", "200"), ("default", ""), ("notes", tab_notes["ports"])]))
    ])

    frequency_options = ["Daily", "Weekly", "Monthly"]

    sites_to_add = []
    emails_to_add = []


    def no_values_message(self, tab_name, message=None):
        no_domains_msg = "No valid values found in tab named '{0}'. Some suggestions for you: <ul><li>Check that the correct tab was specified</li><li>Check that the tab contains valid information</li> <li>Specify a new tab</li> <li>Delete the existing '{0}' tab completely (a new version will be recreated)</li> <li>Restore an old version of the tab using Google Sheets Version History</li></ul>".format(tab_name)
        message = message if message else no_domains_msg
        return message

    def get_mapping_list(self, mapping, key):
        """ returns list of corresponding values from the mapping TODO improve name and description - this actually converts a mapping dict into a google sheet compatible row"""
        list_of_values = [mapping[item][key] for item in mapping]
        return list_of_values

    def create_default_tabs(self, dashboard, emails, domains, form_email=None, form_sites=None,
                            form_email_list=None, update="Run Now"):
        """ create dashboard, email and domain tabs and populate with example content, if they do not exist"""

        self.create_dashboard_tab(dashboard)
        self.create_domains_tab(domains, form_sites)
        self.create_email_tab(emails, form_email_list)
        self.create_update_tab(update)

    def create_update_tab(self, tab_name):
        """ insert a new tab that includes the update sheet url and sets its colour"""

        self.update_tab_name = tab_name
        tab_colour = self.insert_colour((153, 0, 255))  # purple
        self.update_sheet_id = self.create_sheet(tab_name, index=4, tab_colour=tab_colour)

        head_request = self.set_fmt_header_req(self.update_sheet_id, end_column=1)
        column_width = self.set_column_width(self.update_sheet_id, 220, end_index=1)
        comment = self.create_note_request(self.update_sheet_id, self.tab_notes["update"])
        self.batch_update([head_request, column_width, comment])

        data_value_list = []
        header = "Update Dashboard and Emails"
        refresh = self.refresh_link_cells(0)
        log_date = self.insert_date_now()

        data_value_list.append([header])
        data_value_list.extend(refresh)
        data_value_list.extend(log_date)

        self.insert_values(tab_name, data_value_list)

    def create_domains_tab(self, tab_name, form_sites=None):
        """ checks if a tab exists of the same name in the sheet, if not create it, else returns its id """

        self.domains_tab_id = self.get_sheet_id(tab_name)

        if self.domains_tab_id:  # tab exists
            self.sites_to_add = form_sites  # store sites to add
        else:  # create tab
            self.domains_tab_id = self.create_sheet(tab_name, index=2)  # create sheet
            header_row = self.domains_header  # create header  with name "Domains"
            if form_sites:
                new_domain_mapping = deepcopy(self.domain_mapping)
                form_sites = [[site] for site in form_sites]
                new_domain_mapping["domains"]["default"] = form_sites
                updated_domain_row = new_domain_mapping["domains"]["default"]

                values = [header_row]  # cast to an extra list to denote a row
                values.extend(updated_domain_row)  # add the website rows to the header row
                self.insert_values(tab_name, values)
                del new_domain_mapping
            else:
                default_row = [[list_item] for list_item in self.domains_default_row]  # create a new list (ie. row) for each item in the list
                values = [header_row]  # cast to an extra list to denote a row
                values.extend(default_row)  # add the website rows to the header row
                self.insert_values(tab_name, values)

            # format header
            head_request = self.set_fmt_header_req(self.domains_tab_id, end_column=len(header_row))
            protect_request = self.set_protected_cells(self.domains_tab_id, end_row_index=1,
                                                       end_col_index=len(header_row))
            self.batch_update([head_request, protect_request])

            # width
            width_list = []
            for index, item in enumerate(self.domain_mapping):
                width = self.domain_mapping[item]["width"]
                column_width = self.set_column_width(self.domains_tab_id, width, start_index=index)
                width_list.append(column_width)
            self.batch_update(width_list)
            domain_comment = self.create_note_request(self.domains_tab_id, self.domain_mapping["domains"]["notes"],
                                                      list(self.domain_mapping).index("domains"))
            port_comment = self.create_note_request(self.domains_tab_id, self.domain_mapping["ports"]["notes"],
                                                    list(self.domain_mapping).index("ports"))
            self.batch_update([domain_comment, port_comment])

        self.domains_tab_name = tab_name
        return self.domains_tab_id


    def list_before_blanks(self, big_list, consecutive_blanks):
        """ return only the part of the list that occurs before the number of consecutive blanks specified.
        this is used to ensure the footer is not included when retrieving values from sheets """
        blanks_count = 0
        updated_big_list = []
        for row in big_list:
            if not row:
                updated_big_list.append(row)
                blanks_count += 1
                if blanks_count >= consecutive_blanks:
                    break  # stop adding items
                # else:
                #     count = 0
                    # updated_big_list.append(row)
            else:
                updated_big_list.append(row)
                blanks_count = 0  # reset back to zero - looking for consecutive blanks

        return updated_big_list[:-consecutive_blanks]  # remove the last n rows - this should be the number of consecutive blanks specified

    #     if row starts with blank, flag = 1, next loop: if row is blank and add 1 to count, if count matches blanks, stop, else, set flag back to zero

    def get_email_contacts(self):
        """ get the contacts from the specific sheets in the form of a contact object.
        inserts default values if cells are left empty"""

        second_row_range = "{0}!A2:D".format(self.email_tab_name)
        recipients = self.get_values(second_row_range) if self.get_values(second_row_range) else []
        # sheet_recipient_len = len(recipients)
        # recipients = self.list_before_blanks(recipients, 2)
        if self.emails_to_add:
            # form_emails = [[email] for email in self.emails_to_add]
            recipients.extend(self.emails_to_add)
            # next_row_range = "{0}!A{1}".format(self.email_tab_name, sheet_recipient_len + 1)
            # self.insert_values(next_row_range, recipients)

        if recipients:
            new_list = []
            for row in recipients:
                # insert trailing spaces - if row length is less than header length
                if len(row) < len(self.email_header):
                    for i in range(len(self.email_header) - len(row)):
                        row.insert((len(row) + 1), "")
                for item in self.email_header:
                    index = self.email_header.index(item)
                    if not row[index]:  # if an item is empty, insert the corresponding default value
                        row[index] = self.email_default_row[index]
                contact_obj = {key: value for key, value in zip(self.email_mapping, row)}  # contact object uses email mapping keys
                contact_obj["priority"] = self.get_priority_key(contact_obj["priority"])
                new_list.append(contact_obj)
            return new_list
        else:
            print("No email recipients were returned from the sheet")
            # sys.exit(1)
            # print("did not exit")
            return None

    def update_email_tab(self, recipients):
        """ update the emails contacts tab now that missing fields have been populated and last send date included"""
        # second_row_range = "{0}!A2:D".format(self.email_tab_name)
        update_list = []
        # recipients = self.list_before_blanks(recipients, 2)

        for contact in recipients:
            cat_key = contact["priority"]  # store the category key for the priority
            google_priority = self.get_priority_key(contact["priority"], reverse=True)  # convert priority key to dropdown values
            contact["priority"] = google_priority  # change the priority value to the google friendly version
            contact_values = [value for value in contact.values()]  # return the object values in a list
            update_list.append(contact_values)
            contact["priority"] = cat_key  # revert back to the original category key for priority
            print(contact_values)

        # add header to beginning
        header = self.email_header
        update_list.insert(0, header)


        self.insert_values(self.email_tab_name, update_list)

        # add the dropdowns into the GoogleSheet
        self.insert_drop_downs("priority", recipients=recipients, start_column=list(self.email_mapping.keys()).index("priority"))
        self.insert_drop_downs("frequency", recipients=recipients, start_column=list(self.email_mapping.keys()).index("frequency"))

    def get_priority_key(self, sheet_value, reverse=False):
        """ return the python key from the sheet key """
        if not reverse:
            for cat_key in self.cat_priority:
                if self.cat_priority[cat_key]["validation"] == sheet_value:  # convert the sheet dropdown value to the site category key used in the rest of the application
                    return cat_key
            else:
                return sheet_value
        else:
            for cat_key in self.cat_priority:
                if cat_key == sheet_value:
                    return self.cat_priority[cat_key]["validation"]

    def get_spreadsheet_title(self):
        request = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id)
        response = request.execute()
        title = response["properties"]["title"]
        return title

    def get_sheet_info(self):
        request = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id)
        response = request.execute()
        sheet_list = response["sheets"]
        titles = [sheet["properties"]["title"] for sheet in sheet_list]
        ids = [sheet["properties"]["sheetId"] for sheet in sheet_list]

        sheet_info = {title: ids for title, ids in zip(titles, ids)}
        return sheet_info

    def create_email_tab(self, tab_name, form_email_list=None):
        """ checks if a tab exists of the same name in the sheet, if not create it, else returns its id """

        self.email_tab_id = self.get_sheet_id(tab_name)

        email_values_list = []
        if form_email_list:
            for email_obj in form_email_list:
                list_item_email_mapping = deepcopy(self.email_mapping)
                for key in email_obj:
                    if key:
                        list_item_email_mapping[key]["default"] = email_obj[key]
                updated_email_row = self.get_mapping_list(list_item_email_mapping,
                                                          "default")  # create list of default values from mapping
                email_values_list.append(updated_email_row)

        if self.email_tab_id:
            self.emails_to_add = email_values_list
        else:
            self.email_tab_id = self.create_sheet(tab_name, index=1)  # create sheet

            # insert placeholder header values
            header_row = self.email_header  # create header

            if form_email_list:
                email_values_list.insert(0, header_row)
                self.insert_values(tab_name, email_values_list)  #

            else:
                default_row = self.email_default_row
                self.insert_values(tab_name, [header_row, default_row])  #



            # format header and protect header and placeholder
            head_request = self.set_fmt_header_req(self.email_tab_id, end_column=len(header_row))
            protect_request = self.set_protected_cells(self.email_tab_id, end_row_index=1, end_col_index=len(self.email_header))  # protect the header
            self.batch_update([head_request, protect_request])

            # format column width
            width_list = []
            for index, item in enumerate(self.email_mapping):
                width = self.email_mapping[item]["width"]
                column_width = self.set_column_width(self.email_tab_id, width, start_index=index)
                width_list.append(column_width)
            self.batch_update(width_list)
            email_comment = self.create_note_request(self.email_tab_id, self.email_mapping["email"]["notes"], list(self.email_mapping).index("email"))
            priority_comment = self.create_note_request(self.email_tab_id, self.email_mapping["priority"]["notes"], list(self.email_mapping).index("priority"))
            frequency_comment = self.create_note_request(self.email_tab_id, self.email_mapping["frequency"]["notes"], list(self.email_mapping).index("frequency"))
            # email_comment = self.create_note_request(self.email_tab_id, self.tab_notes["emails"], list(self.email_mapping).index("email"))
            # self.batch_update(email_comment)
            self.batch_update([email_comment, priority_comment, frequency_comment])

        self.email_tab_name = tab_name
        return self.email_tab_id


    def insert_comments(self):
        pass

    def create_note_request(self, sheet_id, content, col_start=0):
        request = {
          "updateCells": {
            "range": {
              "sheetId": sheet_id,
              "startRowIndex": 0,
              "endRowIndex": 1,
              "startColumnIndex": col_start,
              "endColumnIndex": col_start + 1
            },
            "rows": [
              {
                "values": [
                  {
                    "note": content
                  }
                ]
              }
            ],
            "fields": "note"
          }
        }

        return request


    def insert_drop_downs(self, dropdown, recipients=None, quantity=1, start_row=1, start_column=1):
        priority_dropdown_list = [{"userEnteredValue": "{0}".format(self.cat_priority[key]["validation"])} for key in self.cat_priority]  # populate list from priority ordered dictionary
        frequency_dropdown_list = [{"userEnteredValue": "{0}".format(item)} for item in self.frequency_options]  # populate from frequency options

        if dropdown == "priority":
            dropdown_list = priority_dropdown_list
        elif dropdown == "frequency":
            dropdown_list = frequency_dropdown_list
        else:
            dropdown_list = dropdown  # if it's not in the pre-defined lists, maintain the item rather than remove (so the user knows they've messed up)

        qty = len(recipients) if recipients else quantity
        end_row = start_row + qty
        end_column = start_column + 1
        email_tab_id = self.email_tab_id  # used to be tab name

        dropdown_request = {
            "setDataValidation": {
                "range": {
                    "sheetId": email_tab_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": start_column,
                    "endColumnIndex": end_column
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": dropdown_list
                    },
                    "inputMessage": "Select a value from the drop down list",
                    "strict": True,
                    "showCustomUi": True
                }
            }
        }

        self.batch_update(dropdown_request)

    @staticmethod
    def insert_colour(rgb_tuple):
        """ return the colour dictionary needed by sheets api from standard rgb tuple """
        rgb_decimals = {
            "red": (rgb_tuple[0]/255),
            "green": (rgb_tuple[1]/255),
            "blue": (rgb_tuple[2]/255)
        }
        return rgb_decimals

    rgb_blue = conversions.insert_colour((98, 149, 234))
    rgb_yellow = conversions.insert_colour((255, 255, 0))
    rgb_red = conversions.insert_colour((210, 3, 0))
    rgb_orange = conversions.insert_colour((233, 156, 64))
    rgb_green = conversions.insert_colour((117, 177, 89))
    rgb_white = conversions.insert_colour((255, 255, 255))
    rgb_black = conversions.insert_colour((0, 0, 0))
    rgb_l_red = conversions.insert_colour((245, 203, 203))
    rgb_l_orange = conversions.insert_colour((250, 209, 166))
    rgb_l_green = conversions.insert_colour((222, 237, 216))

    def update_site_row_colours(self, sorted_site_list):
        """ clear previous colours and update rows with the new latest colours"""
        request_list = []
        start_index = 1  # included

        for category in sorted_site_list:
            if sorted_site_list[category]:
                cat_colour = self.cat_priority[category]["rows"]
                cat_qty = len(sorted_site_list[category])  # number of sites in the category
                end_index = start_index + cat_qty
                next_request = self.create_fmt_next_req(start_index, end_index, cat_colour)
                request_list.append(next_request)
                start_index = end_index

        clear_sheet_request = self.create_fmt_next_req(1, None, self.rgb_white)  # remove old background colours before re-inserting
        request_list.insert(0, clear_sheet_request)

        self.batch_update(request_list)

    def protect_header(self, sheet_id, start_index=0, end_index=None, warning=True):
        """ protect all the headers in one batch request?"""

    def set_protected_cells(self, sheet_id, start_row_index=0, end_row_index=1, start_col_index=0, end_col_index=None, warning=True):
        request_item = {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_index,
                        "endRowIndex": end_row_index,
                        "startColumnIndex": start_col_index,
                        "endColumnIndex": end_col_index,
                    },
                    "description": "Protecting specified cells",
                    "warningOnly": warning
                }
            }
        }

        return request_item

    def set_column_width(self, sheet_id, pixel_width, start_index=0, end_index=None):
        """ auto set column widths """
        end_index = end_index if end_index else start_index + 1
        request_item = {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_index,
                    "endIndex": end_index
                },
                "properties": {
                    "pixelSize": pixel_width
                },
                "fields": "pixelSize"
            }
        }

        return request_item

    def create_fmt_next_req(self, start_row, end_row, colour):
        """ format given site rows with a given background colour"""
        request_item = {
            "repeatCell": {
                "range": {
                    "sheetId": self.dashboard_tab_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(self.site_keys)
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": colour
                    }

                },
                "fields": "userEnteredFormat(backgroundColor)"
            }
        }

        return request_item

    @staticmethod
    def set_fmt_header_req(sheet_id, bg_colour=rgb_blue, text_colour=rgb_white, end_column=1):

        request_item = {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": end_column
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "foregroundColor": text_colour,
                            "bold": True
                        },
                        "backgroundColor": bg_colour
                    }

                },
                "fields": "userEnteredFormat(textFormat, backgroundColor)"
            }
        }

        return request_item

    def set_fmt_date_request(self, header_key):

        date_format_request = {
            "repeatCell": {
                "range": {
                    "sheetId": self.dashboard_tab_id,
                    "startRowIndex": 1,
                    "endRowIndex": None,
                    "startColumnIndex": self.site_keys.index(header_key),
                    "endColumnIndex": None
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "DATE",
                            "pattern": "dd mmm yyyy at hh:mm:ss"
                        }
                    }
                },
                "fields": "userEnteredFormat(numberFormat)"
            }
        }

        return date_format_request

    cat_priority = {
        "expired": {"header": rgb_red, "rows": rgb_l_red, "validation": "Expired Only"},
        "one_day": {"header": rgb_red, "rows": rgb_l_red, "validation": "24 hours"},
        "two_day": {"header": rgb_red, "rows": rgb_l_red, "validation": "48 hours"},
        "one_wk": {"header": rgb_red, "rows": rgb_l_red, "validation": "1 week"},
        "two_wk": {"header": rgb_red, "rows": rgb_l_red, "validation": "2 weeks"},
        "one_mth": {"header": rgb_orange, "rows": rgb_l_orange, "validation": "1 month"},
        "two_mth": {"header": rgb_orange, "rows": rgb_l_orange, "validation": "2 months"},
        "three_mth": {"header": rgb_green, "rows": rgb_l_green, "validation": "3 months"},
        "six_mth": {"header": rgb_green, "rows": rgb_l_green, "validation": "6 months"},
        "six_plus": {"header": rgb_green, "rows": rgb_l_green, "validation": "All Certificates"}
    }

    def batch_update(self, request_list):
        """ takes lists of requests to be sent as a batch """
        request_body = {
            "requests": [
                request_list
            ]

        }

        request_list = self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=request_body)
        response = request_list.execute()

    def format_dashboard(self, sorted_site_list):
        """ manages formatting of the date inserted into the sheet:
        - sets the colour of the header to match the highest priority,
        - sets the date format for the sheet and
        - updates the site row colours"""

        # Format header
        next_priority = conversions.next_ssl_expiration(sorted_site_list)
        if next_priority:
            header_colour = self.cat_priority[next_priority]["header"]
            head_request = self.set_fmt_header_req(self.dashboard_tab_id, header_colour, end_column=len(self.site_keys))
            expiry_request = self.set_fmt_date_request("expiry")  # format the date in the corresponding column of the sheet
            start_request = self.set_fmt_date_request("start")  # format the date in the corresponding column of the sheet

            self.batch_update([head_request, expiry_request, start_request])

            # Format site rows
            self.update_site_row_colours(sorted_site_list)  # updates the row colours for each site
        else:
            print("The next expiration could not be identified. The list provided was: {0}".format(sorted_site_list))
            exit(1)

    def get_dashboard_url(self):
        sheet_id = self.spreadsheet_id
        dashboard_id = self.get_sheet_id("Dashboard")
        sheet_url = "https://docs.google.com/spreadsheets/d/{0}/#gid={1}".format(sheet_id, dashboard_id)
        return sheet_url

    def get_sheet_id(self, tab_name):
        """ get the worksheet id from the name """
        a1_range = "{0}!A1".format(tab_name)

        try:
            request = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id, ranges=str(a1_range))
            response = request.execute()
            sheet_id = response["sheets"][0]["properties"]["sheetId"]  # extracts sheetId
            return sheet_id
        except HttpError as err:
            print("sheet id not found. error message: {}".format(err.content))
            return None

    def get_domains(self):
        """ get the results object from spreadsheet and return the cell values """
        domains = []
        domains_range = self.domains_tab_name
        domains_from_sheet = self.get_values(domains_range) if self.get_values(domains_range) else []

        if self.sites_to_add:  # Add to domains list and append to end of the domains tab (forms to efficient)
            form_sites = [[site] for site in self.sites_to_add]  # format each site for google sheet
            domains.extend(form_sites)  # add new site to domains list
            next_row_range = "{0}!A{1}".format(self.domains_tab_name, len(domains_from_sheet) + 1)  # find bottom of existing sheet
            self.insert_values(next_row_range, form_sites)  # inserts new sites into bottom of existing

        if domains_from_sheet:
            domains.extend(domains_from_sheet)

        if domains:
            for row in domains:
                if len(row) < len(self.domains_header):
                    for i in range(len(self.domains_header) - len(row)):
                        # row.insert((len(row) + 1), "")
                        row.append("")
            return domains
        else:
            print("no domains found when getting domains")
            return None

    def get_values(self, sheet_range):
        """ get the results object from spreadsheet and return the cell values """
        if "!" not in sheet_range:
            sheet_range = "{0}!A1:Z1000".format(sheet_range)  # if a full range is not provided, give max API range

        request = self.service.spreadsheets().values().get(range=sheet_range, spreadsheetId=self.spreadsheet_id)
        response = request.execute()  # full spreadsheet object
        if "values" in response:
            return response['values']  # cell values from spreadsheet object
        else:
            print("Error: no values were returned within range: {0}".format(response["range"]))
            return None

    def create_sheet(self, title, index=None, tab_colour=None):
        """ adds new sheet to existing spreadsheet. returns the new sheetId. Sets the tab color for the sheet """

        if tab_colour:
            red, blue, green = tab_colour.values()
            tabColor = {
                "red": red,
                "green": blue,
                "blue": green
            }
        else:
            tabColor = None

        batch_update_spreadsheet_request_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": title,
                            "index": index,
                            "tabColor": tabColor
                        }
                    }
                }
            ]
        }

        try:
            request = self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=batch_update_spreadsheet_request_body)
            response = request.execute()
            new_sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
            print("new sheet id: " + str(new_sheet_id))
        except HttpError as err:
            if "already exists" in str(err.content):
                new_sheet_id = self.get_sheet_id(title)
                # self.clear_sheet(dashboard_title)
            else:
                error_msg = str(err.content)
                print("unable to create the google sheet titled {0}. Error message is: {1}".format(title, error_msg))
                new_sheet_id = None

        return new_sheet_id

    def clear_sheet(self, sheet_range):
        """ clear an existing sheet """

        if "!" not in sheet_range:
            sheet_range = "{0}!A1:Z1000".format(sheet_range)  # if a full range is not provided, give max API range

        try:
            request = self.service.spreadsheets().values().clear(spreadsheetId=self.spreadsheet_id, range=sheet_range)
            response = request.execute()
        except HttpError as err:
            error_msg = str(err.content)
            print("issue occured when clearing google sheet titled {0}. Error message is: {1}".format(sheet_range, error_msg))

    def create_dashboard_tab(self, dashboard_title, index=0):
        """ create the dashboard sheet if the spreadsheet already exists, clear the values and re-insert it (i.e. update the content)
        takes dashboard title as an argument and optional index position for the new tab"""

        try:
            self.dashboard_tab_id = self.create_sheet(dashboard_title, index)  # create sheet and store sheet id

            # set column widths
            width_list = []
            for map_index, item in enumerate(self.dashboard_mapping):
                width = self.dashboard_mapping[item]["width"]
                column_width = self.set_column_width(self.dashboard_tab_id, width, start_index=map_index)
                width_list.append(column_width)
            self.batch_update(width_list)
            dashboard_comment = self.create_note_request(self.dashboard_tab_id, self.dashboard_mapping["url"]["notes"], list(self.dashboard_mapping).index("url"))
            # comment = self.create_note_request(self.dashboard_tab_id, self.tab_notes["dashboard"])
            self.batch_update(dashboard_comment)

        except HttpError as err:
            if "already exists" in str(err.content):
                self.dashboard_tab_id = self.get_sheet_id(dashboard_title)
                # self.clear_sheet(dashboard_title)
            else:
                error_msg = str(err.content)
                print("Error when creating google sheet titled {0}. Error message is: {1}".format(dashboard_title, error_msg))
                raise

        self.dashboard_tab_name = dashboard_title
        self.dashboard_url = "https://docs.google.com/spreadsheets/d/{0}/#gid={1}".format(self.spreadsheet_id, self.dashboard_tab_id)

        return self.dashboard_tab_id

    def update_dashboard(self, values_list):
        """update the dashboard - inserts dashboard header and updates all the SSL data """
        self.clear_sheet(self.dashboard_tab_name)
        values_list.insert(0, self.dashboard_header)  # insert the header at the beginning
        log_date = self.insert_date_now()
        values_list.extend(log_date)  # add time and date at the end in UTC
        # values_list.extend(self.refresh_link_cells())
        values_list.extend(self.refresh_link_cells(2))
        self.insert_values(self.dashboard_tab_name, values_list)
        return log_date[1][0]  # return time now from log to be included in the HTTP request

    def insert_date_now(self):
        """ return the date now ready to be inserted into a values list
        date is inserted on a separate row with one row of space"""
        time_now = datetime.utcnow()
        local_tz = pytz.timezone("Europe/London")
        local_time = time_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        log_format = ("%Y/%m/%d %T")
        log_time = "Last updated: {0} {1}".format(local_time.strftime(log_format), str(local_tz))
        return [""], [log_time]  # includes a blank row first. Values should .extend() the value list to be written to the sheet

    def get_refresh_link(self):

        address = self.checker_domain
        method = "/sheet-update"
        # sheet_id = self.spreadsheet_id
        # if self.forgive:
        forgive_param = "true" if self.forgive else "false"  # convert to lowercase for url parameter
        # forgive_param = urllib.parse.quote({'forgive': self.forgive})
        tab_params = '?sheetid={0}&dashboard={1}&emails={2}&domains={3}&forgive={4}'.format(self.spreadsheet_id, self.dashboard_tab_name, self.email_tab_name, self.domains_tab_name, forgive_param)
        # params = [("sheetid", self.spreadsheet_id), ("dashboard", self.dashboard_tab_name), ("emails", self.email_tab_name), ("domains", self.domains_tab_name)]
        # params_safe = urllib.parse.quote(params)

        # params_safe = urllib.parse.quote(tab_params)
        # hyperlink = address + method + params_safe
        hyperlink = address + method + tab_params
        print("hyperlink is : ", hyperlink)

        return hyperlink

    def refresh_link_cells(self, blank_rows=0):
        """ return a hyperlinked cell to re-run SSL checker. adds the number of blank rows specified. this needs to be inserted using
         the insert values function() """

        link_text = "Click to re-run SSL Checker"

        hyperlink = self.get_refresh_link()

        blanks = [[""] for item in range(blank_rows)]
        hyperlink_value = [['=HYPERLINK("{0}", "{1}")'.format(hyperlink, link_text)]]

        # hyperlink_value.insert(0, blanks)
        values = blanks + hyperlink_value

        # insert_values = blanks.append(hyperlink_value)
        return values

    def append_sites(self, sheet_range, sites_list: list):
        """for each item in values, create a new row"""
        values = [[item] for item in sites_list]
        # self.append_values(sheet_range, values)
        self.insert_values(sheet_range, values, append=True)


    def insert_values(self, sheet_range, values, append=False):

        if append:
            print("Appending values to sheet (overwrite == False). Sheet range: {}".format(sheet_range))

        # insert_data_option = "OVERWRITE" if overwrite else "INSERT_ROWS"  # insert rows at the end if overwrite is false

        if "!" not in sheet_range:
            sheet_range = "{0}!A1".format(sheet_range)  # if a full range is not provided, assume the range starts at A1

        body = {
            'values': values
        }

        if not append:
            request = self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheet_id, range=sheet_range, valueInputOption="USER_ENTERED", body=body)
            response = request.execute()
        else:
            # use append service: https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/append
            request = self.service.spreadsheets().values().append(spreadsheetId=self.spreadsheet_id, range=sheet_range, valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body)
            response = request.execute()

        return response

    def delete_rows(self, sheet_id, row_numbers: list):
        """ delete multiple rows from a google sheet using a list of row indexes.
        this function generates a new batch request for every new row"""
        batch_requests = []
        for index, row in enumerate(
                sorted(row_numbers)):  # ensure the lowest number goes first and get index number for each request
            batch_requests.append(self.delete_row_request(sheet_id,
                                                          row - index))  # remove current index from initial index to acknowledge for the last deleted row

        self.batch_update(batch_requests)

    def delete_row_request(self, sheet_id, start_index):
        """ generate a delete row batch request"""
        delete_request = {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_index,
                    "endIndex": start_index + 1
                }
            }
        }

        return delete_request

    @staticmethod
    def google_time(timestamp):
        """ convert the javascript timestamps into a ts_to_readable date format for the email"""
        dt = datetime.fromtimestamp(timestamp)
        date = conversions.to_london_time(dt)
        # date = dt.astimezone(pytz.timezone("Europe/London"))
        human_format = "%Y/%m/%d %T"
        google_dt = date.strftime(human_format)
        # google_dt = dt.strftime(human_format)
        return google_dt





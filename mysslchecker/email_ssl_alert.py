import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from collections import OrderedDict
import conversions
import requests
import os
import time
import tldextract

class Message:
    """ stores information unique to each message (to avoid clashes during threading)"""
    def __init__(self, to, subject):
        self.to = to
        self.subject = subject
        self.eml_body = None  # html added to this attribute along the way


class SendEmail:

    def __init__(self, site_list, dashboard_url, spreadsheet_name, refresh_url):
        self.site_list = site_list
        self.dashboard_url = dashboard_url
        self.refresh_url = refresh_url
        self.spreadsheet_name = spreadsheet_name
        self.eml_from = os.getenv("SMTP_FROM")
        self.eml_subject = "SSL Update"
        self.send_by = os.getenv("SSL_SEND_BY")  # "api" or "smtp"
        self.smtp_server = os.getenv("2GO_SMTP_SERVER", os.getenv("MG_SMTP_SERVER"))
        self.smtp_login = os.getenv("2GO_SMTP_LOGIN", os.getenv("MG_SMTP_LOGIN"))
        self.smtp_pw = os.getenv("2GO_SMTP_PW", os.getenv("MG_SMTP_PW"))

    def create_email_header(self, eml_to, eml_from, eml_subject):
        """ MIME header needs to be replaced (cannot be overwritten) """

        mime = MIMEMultipart()
        mime["To"] = eml_to
        mime["From"] = eml_from
        mime["Subject"] = eml_subject

        return mime


    # email subject
    msg_subject_expired = "SSL Checker Results: You have {0} expired, invalid or unreachable SSL {2}"
    msg_subject_urgent = "SSL Checker Results: You have {0} SSL {2} expiring in the next {1}"
    msg_subject_std = "SSL Checker Results: You have {0} SSL {2} expiring in the next {1}"

    # email introduction
    msg_html_start = """
        <html>
          <body>
            <p>Hi {0}!</p>
            <p>Here are the latest SSL results for your spreadsheet, <a href="{1}">{2}</a>:</p>
        """

    # category introductions
    msg_html_category_low = """
                            <p>You have {0} SSL {2} expiring in excess of <strong>{1}</strong> from now. Obviously, no panic required for these: </p>
                        """

    msg_html_category_std = """
                        <p>You have {0} SSL {2} expiring in the next <strong>{1}</strong>:</p>
                    """

    msg_html_category_urg = """
                            <p><strong><font color="red">URGENT:</font></strong> You have {0} {2} expiring in the next <strong>{1}</strong>:</p>
                        """

    msg_html_category_exp = """
                            <p>You have {0} <strong>expired</strong> {2}:</p>
                            """

    msg_html_category_invalid = """<p>You have {0} <strong>invalid</strong> {1}. More information can be found in your Google sheet:</p>"""

    msg_html_category_missing = """<p>You have {0} <strong>missing or unreachable</strong> {1}:</p>"""

    msg_html_category_err = """
                                <p>You have {0} invalid or missing {2}:</p>
                                """

    # category lists
    msg_list_tags = ("""<ol>\n{0}</ol>""", """<ul>\n{0}</ul>""")  # ordered list or unordered list

    msg_html_list = """ <li>{0} in {2} on {3} --> {4}</li> \n"""  # sitename (url) on date

    msg_html_list_exp = """ <li>{0} with subject: {1} expired {2} ago on {3} --> {4}</li> \n"""  # sitename (url) on date

    msg_html_list_invalid = """ <li>{0} with subject: {1}, contains invalid SSL data.</li> \n"""

    msg_html_list_missing = """ <li>{0} has no reachable SSL data. </li> \n"""

    # email outro
    msg_html_outro = """
                <p><strong>Full Google sheet</strong><br/> To view the full list, or change your email alert settings, visit the <a href="{0}">Google sheet</a>. 
                </p>
                <p><strong>Run SSL Checker again</strong><br/> To run SSL Checker again visit the <a href="{1}">update form</a>. 
                </p>
                <p> You've been using SSL Checker, I'm here all week, try the veal. </p>

              </body>
            </html>
            """

    custom_category = OrderedDict([
        # consists of key, email template and a ts_to_readable string to describe the key in the email
        ("expired", (msg_html_category_exp, msg_subject_expired, None)),
        ("one_day", (msg_html_category_urg, msg_subject_urgent, "24 HOURS!")),
        ("two_day", (msg_html_category_urg, msg_subject_urgent, "48 hours")),
        ("one_wk", (msg_html_category_urg, msg_subject_urgent, "week")),
        ("two_wk", (msg_html_category_urg, msg_subject_urgent, "two weeks")),
        ("one_mth", (msg_html_category_std, msg_subject_std, "month")),
        ("two_mth", (msg_html_category_std, msg_subject_std, "two months")),
        ("three_mth", (msg_html_category_std, msg_subject_std, "three months")),
        ("six_mth", (msg_html_category_std, msg_subject_std, "six months")),
        ("six_plus", (msg_html_category_low, msg_subject_std, "six months")),
        ]
    )

    subject_lines = {
        "expired": msg_subject_expired,
        "one_day": msg_subject_urgent,
        "two_day": msg_subject_urgent,
        "one_wk": msg_subject_urgent,
        "two_wk": msg_subject_urgent,
        "one_mth": msg_subject_std,
        "two_mth": msg_subject_std,
        "three_mth": msg_subject_std,
        "six_mth": msg_subject_std,
        "six_plus": msg_subject_std
    }

    def remove_tld(self, domain):
        """ split the tld from domain to help with email delivery"""
        result = tldextract.extract(domain)  # https://pypi.org/project/tldextract/2.2.0/
        if result.suffix:
            if result.subdomain and not result.subdomain == "www":
                domain_string = "{0}.{1} (.{2})".format(result.subdomain, result.domain, result.suffix)
            else:
                domain_string = "{0} (.{1})".format(result.domain, result.suffix)
        else:
            domain_string = result.domain  # no suffix if it's not a url, so return the whole string (aka 'domain')
        return domain_string

    def email_greeting(self, email: str):
        """ removes from the '@' onwards in an email to create the email greeting"""
        index = email.index("@")
        greeting = email[:index]
        return greeting

    @staticmethod
    def cert_or_certs(cat_length):
        """ returns either singular or plural of 'certificates' based on the number provided """
        if cat_length == 1:
            return "certificate"
        else:
            return "certificates"

    def get_priority_key(self, priority):
        """ returns the category that corresponds to the index position in the dictionary
        (i.e. this returns the key of the highest priority category for a contact"""
        priority_list = [item for item in self.custom_category.keys()]
        return priority_list[int(priority)]

    def insert_html_start(self, msg_obj):
        """ insert the email introduction """
        intro_string = self.msg_html_start.format(self.email_greeting(msg_obj.to), self.dashboard_url, self.spreadsheet_name)  # insert the email address as salutation
        return intro_string

    def insert_missing_html_list(self, cat_site_list):
        """ special case for missing sites"""

        cat_len = len(cat_site_list)
        cert_plural = self.cert_or_certs(cat_len)
        html_cat_intro = self.msg_html_category_missing.format(cat_len, cert_plural)

        list_tags = self.msg_list_tags[0] if len(cat_site_list) > 1 else self.msg_list_tags[1]  # use unordered list if only one site in list
        list_items = ""  # all items in the list wrapped, each wrapper in msg_html_list
        for site in cat_site_list:
            list_item = self.msg_html_list_missing.format(self.remove_tld(site["url"]), site["error"])
            list_items += list_item

        html_list = list_tags.format(list_items)  # insert list into list tags (ol or ul)
        html_category = html_cat_intro + html_list
        return html_category

    def insert_invalid_html_list(self, cat_site_list):
        """ special case for invalid sites"""

        cat_len = len(cat_site_list)
        cert_plural = self.cert_or_certs(cat_len)
        html_cat_intro = self.msg_html_category_invalid.format(cat_len, cert_plural)

        list_tags = self.msg_list_tags[0] if len(cat_site_list) > 1 else self.msg_list_tags[1]  # use unordered list if only one site in list
        list_items = ""  # all items in the list wrapped, each wrapper in msg_html_list
        for site in cat_site_list:
            list_item = self.msg_html_list_invalid.format(self.remove_tld(site["url"]), self.remove_tld(site["name"]), site["error"])
            list_items += list_item
        html_list = list_tags.format(list_items)  # insert list into list tags (ol or ul)
        html_category = html_cat_intro + html_list
        return html_category

    def insert_html_list(self, cat, cat_site_list):
        """ list for a single category """
        intro = self.custom_category[cat]  # hardcode this category_intro key for testing e.g. self.category_intro["expired"]
        cat_len = len(cat_site_list)
        cert_plural = self.cert_or_certs(cat_len)
        html_cat_intro = intro[0].format(cat_len, intro[2], cert_plural)  # number of sites in category & time period (if relevant)

        list_tags = self.msg_list_tags[0] if len(cat_site_list) > 1 else self.msg_list_tags[1]  # use unordered list if only one site in list
        list_items = ""  # all items in the list wrapped, each wrapper in msg_html_list
        for site in cat_site_list:
            readable_date = self.ts_to_readable(site["expiry"])
            if cat == "expired":
                list_item = self.msg_html_list_exp.format(self.remove_tld(site["url"]), self.remove_tld(site["name"]), site["countdown"], readable_date, site["issuer"])
                if "error" in site:
                    list_item = list_item.replace("</li>", "</br><strong>Note:</strong> {0}</li>".format(site["error"]))
            else:
                list_item = self.msg_html_list.format(self.remove_tld(site["url"]), self.remove_tld(site["name"]), site["countdown"], readable_date, site["issuer"])
                if "error" in site:
                    list_item = list_item.replace("</li>", "</br><strong>Note:</strong> {0}</li>".format(site["error"]))
            list_items += list_item

        html_list = list_tags.format(list_items)  # insert list into list tags (ol or ul)
        html_category = html_cat_intro + html_list
        return html_category

    def insert_html_end(self):
        """ insert category into category string and add to message """
        # refresh_link = self.my
        end_string = self.msg_html_outro.format(self.dashboard_url, self.refresh_url)
        return end_string

    def submit_to_smtp_server(self, mime):
        print("smtp send")
        result = None
        try:
            with smtplib.SMTP(self.smtp_server, 587) as server:
                server.starttls()
                server.login(self.smtp_login, self.smtp_pw)
                # print(mime.as_string())
                result = server.sendmail(mime["From"], mime["To"], mime.as_string())  # TESTING
                if result:
                    print("** Error sending to email address: ", result)
                    return False  # if failure, result string contains email addresses
                else:
                    print(mime.as_string())
                    return True  # empty result means the send was successful
        except Exception as err:
            print("** Error during email send to: {0}. Message: {1}".format(mime["To"], err))
            return False


    def create_subject_line(self, next_priority):
        cat_length = len(self.site_list[next_priority])
        cat_name = self.custom_category[next_priority][2]
        cert_plural = self.cert_or_certs(cat_length)
        subject_line = self.custom_category[next_priority][1].format(cat_length, cat_name, cert_plural)
        return subject_line

    def send_email(self, contact):
        """ Takes the list of sites, builds the corresponding email and submits it to email server
        if a recipient has no relevant content, no email is sent """

        last_sent_dt = self.str_to_datetime(contact["last"])
        frequency = contact["frequency"]

        sending_time = conversions.time_to_send(last_sent_dt, frequency)

        if sending_time:
            content_for_recipient = False  # placeholder becomes true if there are sites returned for the recipient
            site_list = self.site_list
            next_priority = conversions.next_ssl_expiration(site_list)

            eml_subject = self.create_subject_line(next_priority)
            eml_to = contact["email"]
            msg_obj = Message(eml_to, eml_subject)

            # self.create_email_header(msg_obj.to, msg_obj.subject)
            msg_obj.eml_body = self.insert_html_start(msg_obj)

            for cat in site_list:
                if site_list[cat]:  # if category isn't empty...
                    if cat == "expired":
                        missing_sites = [site for site in site_list[cat] if site["ssl_status"] == "missing"]
                        invalid_sites = [site for site in site_list[cat] if site["ssl_status"] == "fail"]
                        expired_sites = [site for site in site_list[cat] if site["ssl_status"] == "pass"]
                        if missing_sites:
                            msg_obj.eml_body += self.insert_missing_html_list(missing_sites)  # pass through the category and the sites in the category#
                        if invalid_sites:
                            msg_obj.eml_body += self.insert_invalid_html_list(invalid_sites)  # pass through the category and the sites in the category#
                        if expired_sites:
                            msg_obj.eml_body += self.insert_html_list(cat, expired_sites)  # pass through the category and the sites in the category#
                        content_for_recipient = True  # there is something to send for this content
                    else:
                        msg_obj.eml_body += self.insert_html_list(cat, site_list[cat])  # pass through the category and the sites in the category#
                        content_for_recipient = True  # there is something to send for this content
                if cat == contact["priority"]:  # when category reaches set priority, stop looping.
                    break

            msg_obj.eml_body += self.insert_html_end()
            # msg_obj.eml_body = self.eml_body  # original fix

            if content_for_recipient:
                time.sleep(2)
                success = None
                # print(msg_obj.eml_body)  # print all emails before sending
                if self.send_by == "api":
                    print("send by API")
                    success = self.send_mailgun_api_message(msg_obj)
                else:
                    # send via SMTP Server
                    print("send by smtp")
                    email_mime = self.create_email_header(eml_to=msg_obj.to, eml_from=self.eml_from, eml_subject=msg_obj.subject)
                    email_mime.attach(MIMEText(msg_obj.eml_body, "html"))  # attach constructed html body to message in MIMEText format
                    success = self.submit_to_smtp_server(email_mime)

                if success:
                    # update the last send time
                    contact["last"] = self.send_email_date_now()

        return contact

    def send_mailgun_api_message(self, msg_obj):
        print("api send")
        result = requests.post(
            os.getenv("MG_API_URL"),
            auth=("api", os.getenv("MG_API_KEY")),
            data={"from": self.eml_from,
                  "to": msg_obj.to,
                  "subject": msg_obj.subject,
                  "html": msg_obj.eml_body})
        if result.status_code == 200:
            print("url: ", os.getenv("MG_API_URL"), "key: ", os.getenv("MG_API_KEY"), "from: ", self.eml_from, "to: ", msg_obj.to, "subject: ", msg_obj.subject)
            print("body: ", msg_obj.eml_body)
            return True
        else:
            print("** Error when sending to email address: {0}. Status Code: {1} ({2}). Reason: {3}".format(msg_obj.to, result.status_code, result.text, result.reason))
            return False

    @staticmethod
    def str_to_datetime(sheet_time):
        """ takes the date string from the google sheet email tab and returns a python datetime item """
        try:
            string_format = "%d %b %Y %H:%M:%S"
            dt = datetime.strptime(sheet_time, string_format)
            return dt
        except:
            return sheet_time

    @staticmethod
    def send_email_date_now():
        time_now = datetime.now()
        email_format = "%d %b %Y %H:%M:%S"
        readable_dt = time_now.strftime(email_format)
        return readable_dt

    @staticmethod
    def ts_to_readable(timestamp):
        """ convert the javascript timestamps into a ts_to_readable date format for the email"""
        dt = datetime.fromtimestamp(timestamp)
        # human_format = "%a %d %b %Y at %T"
        date = conversions.to_london_time(dt)
        human_format = "%a %d %b %Y"
        readable_dt = date.strftime(human_format)
        return readable_dt

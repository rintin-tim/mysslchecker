from datetime import datetime
from dateutil import relativedelta
import re
import pytz
# import datetime
import time

"""def get_sorted_categories(site_list):
     # wrap up the sorting and categories into a single method 

    valid_sites = []  # list sites that don't have an error key
    invalid_sites = []  # list sites that do have an error key

    for site in site_list:
        if "expiry" not in site:
            invalid_sites.append(site)
        else:
            valid_sites.append(site)

    sorted_valid_list = sort_sites(valid_sites, "expiry")
    sorted_invalid_list = sort_sites(invalid_sites, "url")  # if sites are invalid, sort them alphabetically
    categorised_list = categorise_sites(sorted_invalid_list + sorted_valid_list)  # add the two lists together and categorise
    # categorised_list = categorise_sites(sorted_valid_list)  # add the two lists together and categorise
    # updated_list = sorted_invalid_list + categorised_list  # o
    # sort valud only
    # return updated_list
    return categorised_list
"""

def get_sorted_categories(site_list):
    """ wrap up the sorting and categories into a single method """

    valid_sites = []  # list sites that don't have an error key
    invalid_sites = []  # list sites that do have an error key
    no_ssl_sites = []

    for site in site_list:
        if "expiry" not in site:
            site["ssl_status"] = "missing"
            no_ssl_sites.append(site)
        elif "error" in site and "PASS" not in site["error"]:  # fail if it doesn't include pass
            site["ssl_status"] = "fail"
            invalid_sites.append(site)
        else:
            site["ssl_status"] = "pass"  # pass if it does include pass or has no errors
            valid_sites.append(site)

    sorted_valid_list = sort_sites(valid_sites, "expiry")
    sorted_invalid_list = sort_sites(invalid_sites, "url")  # if sites are invalid, sort them alphabetically
    sorted_no_ssl_list = sort_sites(no_ssl_sites, "url")
    categorised_list = categorise_sites(sorted_no_ssl_list + sorted_invalid_list + sorted_valid_list)  # add the three lists together and categorise

    return categorised_list


def sort_sites(site_list, key):
    """ sort the sites by key """
    def sort_by(item):
        """ key= function for sorted(). sort by the expiry property """
        return item["{0}".format(key)]

    sorted_site_list = sorted(site_list, key=sort_by, reverse=False)  # order site list by expiration and reverse

    return sorted_site_list


def categorise_sites(site_list):
    """ places sites in ranges according to the time until they expire.
    returns a new object with these categories as keys """

    time_now = datetime.now()
    one_day = time_now + relativedelta.relativedelta(days=+1)
    two_day = time_now + relativedelta.relativedelta(days=+2)
    one_wk = time_now + relativedelta.relativedelta(weeks=+1)
    two_wk = time_now + relativedelta.relativedelta(weeks=+2)
    one_mth = time_now + relativedelta.relativedelta(months=+1)
    two_mth = time_now + relativedelta.relativedelta(months=+2)
    three_mth = time_now + relativedelta.relativedelta(months=+3)
    six_mth = time_now + relativedelta.relativedelta(months=+6)

    results = {
        "expired": [],
        "one_day": [],
        "two_day": [],
        "one_wk": [],
        "two_wk": [],
        "one_mth": [],
        "two_mth": [],
        "three_mth": [],
        "six_mth": [],
        "six_plus": []
    }

    for site in site_list:
        if site["ssl_status"] == "missing":
        # if "expiry" not in site:
            results["expired"].append(site)  # sites with no ssl data are returned in expired
        elif site["ssl_status"] == "fail":
        # elif "error" in site and "PASS" not in site["error"]:
            results["expired"].append(site)  # sites with errors are returned in expired
        else:
            expiry = datetime.fromtimestamp(site["expiry"])
            if expiry < time_now:
                results["expired"].append(site)
            elif time_now <= expiry < one_day:  # python shorthand for: if 'expiry' is between 'timenow' and 'one_day'
                results["one_day"].append(site)
            elif one_day <= expiry < two_day:  # python shorthand for: if 'expiry' is between 'one_day' and 'two_day'
                results["two_day"].append(site)
            elif two_day <= expiry < one_wk:
                results["one_wk"].append(site)
            elif one_wk <= expiry < two_wk:
                results["two_wk"].append(site)
            elif two_wk <= expiry < one_mth:
                results["one_mth"].append(site)
            elif one_mth <= expiry < two_mth:
                results["two_mth"].append(site)
            elif two_mth <= expiry < three_mth:
                results["three_mth"].append(site)
            elif three_mth <= expiry < six_mth:
                results["six_mth"].append(site)
            elif expiry >= six_mth:
                results["six_plus"].append(site)

    return results


def next_ssl_expiration(cat_site_list):
    """ return the category key of the *first* (i.e. highest priority) item - requires a cagtegorised list i.e. categorise_sites() """

    for category in cat_site_list:
        if cat_site_list[category]:
            return category
    else:
        return None


def insert_colour(rgb_tuple):
    """ return the colour dictionary needed by sheets api from standard rgb tuple """

    rgb_decimals = {
        "red": (rgb_tuple[0] / 255),
        "green": (rgb_tuple[1] / 255),
        "blue": (rgb_tuple[2] / 255)
    }

    return rgb_decimals


def valid_email(email):
    """ checks that the email provided is a valid syntax - returns email if true and False if not """
    email_pattern = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"  # https://emailregex.com/
    valid = re.match(email_pattern, email)

    if valid:
        return email
    else:
        return False


def time_to_send(send_date, frequency):
    """ compares the time now to the time of last send and the desired frequency. it returns true if
    time to send, else false """
    time_now = datetime.now()
    if frequency == "Daily":
        relative_delta = relativedelta.relativedelta(days=+1, hours=-2)
    elif frequency == "Weekly":
        relative_delta = relativedelta.relativedelta(weeks=+1, hours=-2)
    elif frequency == "Monthly":
        relative_delta = relativedelta.relativedelta(months=+1, hours=-2)
    else:
        print("dodgy value for frequency {}".format(frequency))
        return False
    # print("send date {} relative_delta {}  time_now {}".format(send_date, relative_delta, time_now))

    try:
        print("relative delta is: ", relative_delta)
        if send_date:
            print("the next send date threshold is: ", send_date + relative_delta)
        if (not send_date) or (send_date + relative_delta < time_now):
            # print("send date {} relative_delta {}  time_now {}".format(send_date, relative_delta, time_now))
            return True
        else:
            return False  # return false if you haven't returned True by now
    except TypeError:
        print("received a TypeError, the send date did not match expected format: {0} - returned False.".format(send_date))
        return False  # exception likely to be because the date value entered into Google has the wrong format


def insert_date_now():
    """ return the date now ready to be inserted into a values list
    date is inserted on a separate row with one row of space"""
    time_now = datetime.utcnow()
    local_tz = pytz.timezone("Europe/London")
    local_time = time_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
    log_format = "%Y/%m/%d %T"
    date_time_now = "{0} {1}".format(local_time.strftime(log_format), str(local_tz))
    # log_time = "Last updated: {0} {1}".format(local_time.strftime(log_format), str(local_tz))
    return date_time_now


def to_london_time(python_dt):
    """return london timezone from python date object"""
    ldn_time = python_dt.astimezone(pytz.timezone("Europe/London"))
    return ldn_time

# def ts_to_readable(timestamp):
#     """ convert the javascript timestamps into a ts_to_readable date format for the email."""
#     dt = datetime.fromtimestamp(timestamp)
#     human_format = "%a %d %b %G at %T"
#     readable_dt = dt.strftime(human_format)
#     return readable_dt

# def get_date_now():
#     time_now = datetime.now()
#     human_format = "%a %d %b %G

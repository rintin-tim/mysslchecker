#! /Library/Frameworks/Python.framework/Versions/3.6/bin/python3.6

import sys
import ssl
from OpenSSL import crypto
from datetime import datetime, timezone
import pytz
import getopt
import socket
from dateutil import relativedelta
import re
from urllib.request import urlopen
from urllib.parse import urlparse
import urllib.error
import json

class Certificate:
    """ creates a certificate object, providing formatted access to the main certificate properties """

    def __init__(self, cert):

        self._x509 = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
        self.expiry = self.get_expiry()
        self.issuer = self.get_issuer()
        self.subject = None  # to add
        self.serial = self.get_serial()
        self.start = self.get_start()
        self.url = None
        self.countdown = self.get_countdown()
        self.subject_org = self.get_organisation("subject")

    def get_expiry(self):
        """ formats the expiry expiry datetime object """
        py_date = self.ssl_property_to_py("expiry")
        formatted_date = self.format_date(py_date)
        return formatted_date

    def ssl_property_to_py(self, x509_property):
        """ returns an x509 date a datetime object """
        if x509_property == "start":
            x509_date = self._x509.get_notBefore().decode('utf-8')
            py_date = self.convert_x509_to_dt(x509_date)
            return py_date
        elif x509_property == "expiry":
            x509_date = self._x509.get_notAfter().decode('utf-8')
            py_date = self.convert_x509_to_dt(x509_date)
            return py_date
        elif x509_property == "issuer":
            binary_issuer = self._x509.get_issuer().get_components()  # returns a tuple of issuer components in binary
            utf8_issuer = [(prop.decode('utf-8'), value.decode('utf-8')) for prop, value in binary_issuer]  # List Comp > Converts binary tuple to utf-8
            return utf8_issuer
        elif x509_property == "serial":
            serial_number = self._x509.get_serial_number()  # returns an integer (see get_serial() for hexcode)
            return serial_number
        elif x509_property == "subject":
            binary_issuer = self._x509.get_subject().get_components()  # returns a tuple of issuer components in binary
            utf8_issuer = [(prop.decode('utf-8'), value.decode('utf-8')) for prop, value in binary_issuer]  # List Comp > Converts binary tuple to utf-8
            return utf8_issuer

        else:
            raise Exception("x509 property not recognised: {0}".format(x509_property))

    def get_issuer(self):
        """ returns formatted string """
        issuer_tuple = self.ssl_property_to_py("issuer")
        formatted_issuer = self.format_issuer(issuer_tuple)
        return formatted_issuer

    @staticmethod
    def format_issuer(components):
        """ formats the decoded component tuple. Creates a single string with each tuple pair ', ' separated.
        Converts issuer codes to full names e.g 'C' to 'Country'. Inserts a character between each key and value
        such as '=' or ':' to aid string readability. Has the option to return a dictionary rather than a
        string to help with API integration. """

        issuer_property = {
            "C": "Country",
            "ST": "State",
            "L": "Location",
            "O": "Organisation",
            "OU": "Organisational Unit",
            "CN": "Common Name"
        }

        # Return a dictionary with the issuer details. Not currently used but could help for API integration
        issuer_dict = {}
        for prop, value in components:
            issuer_dict[prop] = value 

        # Return a string with the issuer details.
        kv_separator = ": "  # char(s) used to separate the key from the value in the output . e.g. ':', '=', '>'
        if issuer_short:
            # issuer_string = ", ".join([issuer_property[key] + kv_separator + value for key, value in reversed(components) if key == "CN" or key == "C"])  # reverse list and return only the country and common name
            issuer_string = ", ".join([value for key, value in reversed(components) if key == "CN"])  # reverse list and return only the common name
        else:
            issuer_string = ", ".join([issuer_property[key] + kv_separator + value for key, value in reversed(components)])

        return issuer_string  # e.g. Country=GB, State=Greater Manchester, Location=Salford, Organisation=COMODO CA Limited

    def get_serial(self):
        serial_number = self.ssl_property_to_py("serial")
        hex_number = format(serial_number, 'x')  # get_serial_number returns integer but hex format is more common to see on internet
        return hex_number

    def get_start(self):
        py_date = self.ssl_property_to_py("start")
        formatted_date = self.format_date(py_date)
        return formatted_date

    @staticmethod
    def convert_x509_to_dt(x509_date):
        """ converts the x509 date format to a python datetime object """
        utc_date = x509_date.replace('Z', "+0000")  # UTC offset 'Z' (Zulu) is not understood by strptime(). This replaces it with the standard notation of "+0000". All x509 dates are UTC.
        py_date = datetime.strptime(utc_date, "%Y%m%d%H%M%S%z")
        return py_date

    @staticmethod
    def format_gmt_offset(off_amount):
        """ takes the requested offset number and returns the offset number required for Etc/GMT as a string
        note the number required for Etc/GMT offset is the *inverse* of normal offsets due to a POSIX bug
        """
        if offset:
            offset_int = int(off_amount)
            if offset_int in range(0, -14):
                offset_string = "+{0}".format(offset_int)
            elif offset_int in range(1, 14):
                offset_string = "-{0}".format(offset_int)  # change positive offsets to negative and vice versa - POSIX bug(!)
            else:
                print("offset value of '{0}' is not in expected range".format(off_amount))
                exit(1)
            return offset_string

        else:
            return offset  # return the existing None value

    def format_date(self, python_date):
        """ format the python date for readability. return a timestamp by default.
        if offset and local provided, offset will be returned """
        date = python_date
        if local and not offset:
            date = python_date.astimezone(pytz.timezone("Europe/London"))
        if offset:
            offset_string = self.format_gmt_offset(offset)
            date = python_date.astimezone(pytz.timezone("Etc/GMT{0}".format(offset_string)))
        if readable:
            human_format = "%c"  # Locale’s appropriate date and time representation: Tue Aug 16 21:30:00 1988 (en_US);
            date = date.strftime(human_format)
        else:
            date = date.timestamp()
        return date

    def get_countdown(self):
        """ return the time until the ssl expires"""
        expiry_time = self.ssl_property_to_py("expiry")
        # expiry_time = datetime.now(timezone.utc)
        # time.sleep(5)
        time_now = datetime.now(timezone.utc)
        remain = relativedelta.relativedelta(expiry_time, time_now)
        if remain.years == 0:
            rem_yr = None
        else:
            rem_yr = "%d year" % remain.years if (remain.years == 1) or (remain.years == -1) else "%d years" % remain.years  # if singular, use singular

        rem_mth = "%d month" % remain.months if (remain.months == 1) or (remain.months == -1) else "%d months" % remain.months
        rem_wks = "%d week" % remain.weeks if (remain.weeks == 1) or (remain.weeks == -1) else "%d weeks" % remain.weeks
        seven = 7 if remain.days >= 0 else -7  # needs to be a minus to get correct modulus if number of days is a minus (i.e. certificate has expired)
        rem_days = "%d day" % (remain.days % seven) if (remain.days % seven == 1) or (remain.days % seven == -1) else "%d days" % (remain.days % seven)  # modulus of dividing days by 7

        if rem_yr:
            countdown_string = "{0}, {1}, {2}, {3}".format(rem_yr, rem_mth, rem_wks, rem_days)  # only show years if years are relevant
        else:
            countdown_string = "{0}, {1}, {2}".format(rem_mth, rem_wks, rem_days)
        return countdown_string

    def get_organisation(self, org_type):
        """
        args:
        - org type:
            - subject (string) - return the organisation name for the certificate subject
            - issuer (string) - return the organisation name for the certificate issuer

        returns organisation name for subject or issuer. if not found, returns common name. if still not found returns 'NA' as a string """

        org_components = self.ssl_property_to_py("{0}".format(org_type))

        for k, v in org_components:
            if k == "O":
                return v
        else:
            for k, v in org_components:
                if k == "CN":
                    return v
            else:
                return "NA"  # implement url


address = sys.argv[1]  # first parameter after script name
options = sys.argv[2:]  # optional arguments passed into the script (all args after the address parameter)

port = 443
readable = False
local = False
expiry = True
start = False
issuer = False
issuer_short = False
number = False
countdown = False
countdown_short = False
# verbose = False
offset = None
subject_name = False
forgiving = False
timeout = 5
forgiving_error = False

error_message = []  # list of strings ?


# TODO cutdown single letter flags!

opts, unknown = getopt.getopt(options, "p:ferlsitncuo:a", ["for", "port=", "expiry", "ts_to_readable", "local", "start", "issuer", "issuershort", "number", "countdown", "countdownshort", "offset=", "forgiving", "timeout=", "all"])  # looks for -p or --port in provided arguments

for opt, arg in opts:
    if opt == ("-p" or "--port"):
        port = int(arg)  # set port from provided arguments
    elif opt == ("-e" or "--expiry"):
        expiry = True
    elif opt == ("-r" or "--ts_to_readable"):
        readable = True
    elif opt == ("-l" or "--local"):
        local = True
    elif opt == ("-s" or "--start"):
        start = True
    elif opt == ("-i" or "--issuer"):
        issuer = True
    elif opt == ("-t" or "--issuershort"):
        issuer_short = True
    elif opt == ("-n" or "--number"):
        number = True
    elif opt == ("-c" or "--countdown"):
        countdown = True
    elif opt == ("-u" or "--countdownshort"):
        countdown_short = True
    elif opt == ("-o" or "--offset"):
        offset = arg
    elif opt == ("-f" or "--for"):
        subject_name = True
    elif opt == "--forgiving":
        forgiving = True
    elif opt == "--timeout":
        timeout = int(arg)
    elif opt == "-a" or opt == "--all":
        local = True
        expiry = True
        start = True
        issuer_short = True
        number = True
        countdown_short = True
        subject_name = True
        # forgiving = True

if unknown:
    error_01 = "Unknown arguments provided: {0}".format(unknown)
    error_message.append(error_01)


# if verbose:
#     print("get certificate from {0}:{1}".format(address, port))


def clean_url(address):
    """ remove the protocol and subdirectorires for uniformity """
    domain_pattern = r"(?i)\b([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}\b"
    domain = re.search(domain_pattern, address)  # return only the domain (in case the protocol is added)
    if domain:
        hostname = domain.group(0)  # strip out any protocol found (and maybe subdirectory)
        # print("cleaning gives me this: {}".format(hostname))
    else:
        hostname = address  # if not matched by RegEx, still pass through, just in case it's valid
    return hostname


hostname = clean_url(address)



def get_pem_cert(hostname, port, timeout, sslv23=False, error_count=0, forgive_flow=False):
    global forgiving_error
    error_count = error_count
    # print("attempt: " + str(error_count))
    if error_count < 2:
        if sslv23:
            context = ssl.SSLContext(
                ssl.PROTOCOL_SSLv23)  # SSLv23 deprecated in Python 3.6 but works see above. UPDATE: use this version to return expired SSLs
        else:
            context = ssl.create_default_context()  # Python Mac OS issue. Install Certificates.command from Applications/Python 3.6 folder or use SSLv23. https://stackoverflow.com/questions/41691327/ssl-sslerror-ssl-certificate-verify-failed-certificate-verify-failed-ssl-c
        try:
            with socket.create_connection((hostname, port), timeout=timeout) as sock:  # create a socket (port and url)
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:  # add a context to the socket (handshake information)
                    pem_cert = ssl.DER_cert_to_PEM_cert(ssock.getpeercert(True))  # use the socket to get the peer certificate
            return pem_cert
        except socket.timeout:
            error_04 = "*Timed out during original certificate retrieval*"
            error_message.append(error_04)
            return None
        except ssl.CertificateError as cert_err:
            error_count += 1
            error_12 = "SSL Certificate error: {0} ".format(cert_err)
            error_message.append(error_12)
            pem_cert = get_pem_cert(hostname, port, timeout, sslv23=True, error_count=error_count)
            if forgive_flow:
                forgiving_error = True
            return pem_cert
        except ssl.SSLError as ssl_err:
            error_count += 1
            # error_13 = "Warning: SSL error: {0} ".format(ssl_err)
            # error_message.append(error_13)
            pem_cert = get_pem_cert(hostname, port, timeout, sslv23=True, error_count=error_count)
            if forgive_flow:
                forgiving_error = True
            return pem_cert
        except:
            # raise
            error_05 = "* Unable to connect to {0}. *".format(hostname)
            error_message.append(error_05)
            return None
    else:
        # error_14 = "* Too many errors encountered - stopped. *".format(hostname)
        # error_message.append(error_14)
        return None


f = open("timeout.txt", "a")
f.write("time out is {0}. forgiveness is {1} \n".format(timeout, forgiving))

f.close()

pem_cert = get_pem_cert(hostname, port, timeout)

if not pem_cert and forgiving:
    try:
        urllib_response = urlopen("http://" + hostname, timeout=timeout)
        final_url = urllib_response.url
        parsed_url = urlparse(final_url)
        if not clean_url(parsed_url.hostname) == hostname:  # if the final url is different to the original, there must be a redirect
            redirect_hostname = urlparse(final_url).hostname
            pem_cert = get_pem_cert(redirect_hostname, port, timeout=timeout, forgive_flow=True)
            if pem_cert and not forgiving_error:
                error_06 = "SOFT PASS: Domain has no valid SSL but a valid SSL was found on the redirected domain: {0}".format(redirect_hostname)
                error_message.append(error_06)
            elif pem_cert and forgiving_error:
                error_16 = "SSL error on redirected domain: {0}".format(redirect_hostname)
                error_message.append(error_16)
            else:
                error_07 = "Redirect: No ssl found on redirected domain {0}"
                error_message.append(error_07)

        else:
            "Redirect: No redirect to check"
    except socket.timeout:
        error_03 = "*Redirect: Timed out during redirect*"
        error_message.append(error_03)
    except urllib.error.URLError:
        pass
    except ssl.CertificateError as err:
        error_10 = "*Redirect: SSL Certificate error: {0}*".format(err)
        error_message.append(error_10)
    except:
        pass

if not pem_cert:
    error_02 = "Could not connect to host: {0} on port: {1}.".format(hostname, port)
    error_message.append(error_02)


# create result log
result_log = {}

if pem_cert and ("BEGIN CERTIFICATE" in pem_cert):
    certificate = Certificate(pem_cert)

    organisation = certificate.get_organisation("subject")

    if subject_name:
        result_log["name"] = certificate.subject_org
    if expiry:
        result_log["expiry"] = certificate.expiry
    if start:
        result_log["start"] = certificate.start
    if issuer or issuer_short:
        result_log["issuer"] = certificate.issuer
    if number:
        result_log["number"] = certificate.serial
    if countdown or countdown_short:
        result_log["countdown"] = certificate.countdown

if error_message:
    error_message.reverse()  # print the last error first
    result_log["error"] = ", ".join(error_message)  # get a single string of errors


print(json.dumps(result_log))




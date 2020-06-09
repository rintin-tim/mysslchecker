class WebMessages:

    def __init__(self, sheet_obj):
        self.sheet_obj = sheet_obj

    def msg_with_error(self, explanation, error):
        """ adds the http error returned by Google to the error message provided to the user"""
        formatted_err = error.replace(r"\n", "<br>")  # replaces new line chars with HTML breaks in the Google message
        formatted_err = formatted_err.replace(r"b'{", "{")  # replaces new line chars with HTML breaks in the Google message
        explanation = """<p>{0}</p>""".format(explanation)
        error_body = """
        <p>Below is the whole error message - sorry, it's a bit messy:</p>
        <p><strong>{0}</strong></p>""".format(formatted_err)
        body = explanation + error_body
        web_message = self.error_boiler_plate_wrap(body)
        return web_message

    def general_err_msg(self, explanation):
        body = """<p>{0}</p>""".format(explanation)
        web_message = self.error_boiler_plate_wrap(body)
        return web_message

    def permissions_msg(self, explanation):
        body = """<p>{0}</p>""".format(explanation)
        web_message = self.error_boiler_plate_wrap(body)
        return web_message

    def error_boiler_plate_wrap(self, body):
        """takes the specific error message and wraps it up in a boiler plate header and footer"""
        wrap_body = """
            <h1>Whoops!</h1>
            {0}
            <p>The ID of the provided Google sheet is: <strong>{1}</strong>. </p>
            <p><a href='https://docs.google.com/spreadsheets/d/{1}' target='_blank' class="btn btn-secondary>Go to Current Dashboard</a></p>
        """.format(body, self.sheet_obj.spreadsheet_id)
        print(wrap_body)  # could be a log file
        return wrap_body

    def redis_ssl_site_result_msg(self, minutes_required):
        title = "<h1>We're all set!</h1>"
        body = "<p>Your sites are being checked and your sheet will be updated automatically. " \
               "Your sheet will be ready in " \
               "a maximum of: {0} minute(s).</p>".format(minutes_required)
        web_message = self.success_boiler_plate_wrap(title, body)
        return web_message

    def redis_dashboard_updating_msg(self):
        title = "<h1>Your dashboard is being updated!</h1>"
        body = "<p>The results have been collected and your dashboard update is underway. Your sheet will be ready in " \
               "less than a minute.</p>"
        web_message = self.success_boiler_plate_wrap(title, body)
        return web_message

    def redis_dashboard_complete_msg(self):
        title = "<h1>Your dashboard has been updated!</h1>"
        body = "<p>The results have been collected and your dashboard is ready. Relevant email notifications are now being scheduled for delivery.</p>"
        web_message = self.success_boiler_plate_wrap(title, body)
        return web_message

    def redis_tidy_msg(self):
        title = "<h1>Your dashboard has been updated!</h1>"
        body = "<p>The results have been collected, your dashboard is ready, email notifications have been scheduled (if relevant), " \
               "we're basically done! SSL Checker is doing some spreadsheet tidy up, but your results can be viewed now. </p>"
        web_message = self.success_boiler_plate_wrap(title, body)
        return web_message

    # TODO not used
    def general_success_msg(self, title, explanation):
        title = """<h1>{0}</h1>""".format(title)
        body = """<p>{0}</p>""".format(explanation)
        web_message = self.success_boiler_plate_wrap(title, body)
        return web_message

    def success_boiler_plate_wrap(self  , title, body):
        """takes the specific message and wraps it up in a boiler plate header and footer"""
        wrap_body = """
            {0}
            {1}
            <p><a href='{2}' target='_blank' class='btn btn-outline-success'>Go to Dashboard</a></p>
        """.format(title, body, self.sheet_obj.dashboard_url)
        print(wrap_body)  # could be a log file
        return wrap_body

    def management_sheet_error(self):
        """ generic message for management sheet issues - does not return the mgmt spreadhseet ID to the user"""
        body = """
            <p>A slight issue occured when trying to store details for this sheet.</p> 
                <p>Good news is your Google Sheet has been updated. The bad news is it will not automatically update in the future... Please contact the system administrator.</p> 
            """
        web_message = self.error_boiler_plate_wrap(body)
        return web_message

    def dashboard_success(self):
        body = """<h1>Update Complete!</h1>
            <p>The results have been collected, your dashboard has been updated and any relevant emails have been scheduled for delivery</p>
            <p>Woohoo!</p> 
            <p>You can view your results by clicking the dashboard button below. </p>
            <p><a href="{0}" target="_blank" class="btn btn-success">Go to Dashboard</a></p>""".format(self.sheet_obj.dashboard_url)
        return body

    @staticmethod
    def redis_error_send_email():
        return "Good news: Your dashboard has been updated successfully. Bad news: A problem occured and email notifications have not been processed. Sorry about that."

    @staticmethod
    def redis_error_tidy():
        return "Good news: Your dashboard has been updated successfully and email notifications have been sent. Bad news: A problem occured and you may not receive future email notifications. Sorry about that."

    @staticmethod
    def progress_page():
        body = """<h1>Update Complete!</h1>
            <p> This is the progress page</p>"""
        print("print progress page")

        return body

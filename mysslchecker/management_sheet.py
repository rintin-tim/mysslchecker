from google_sheet import GoogleSheet
from googleapiclient.errors import HttpError
import time


class ManagementSheet(GoogleSheet):

    def __init__(self, mgmt_sheet_id, mgmt_tab_name, user_sheet_id):
        """ user_sheet_id is the sheet id for the earlier 'MySheet' object"""
        super().__init__(mgmt_sheet_id)
        self.mgmt_sheet_id = mgmt_sheet_id
        self.mgmt_tab_name = mgmt_tab_name
        self.mgmt_tab_id = self.create_management_sheet(mgmt_tab_name)
        self.user_sheet_id = user_sheet_id
        self.mgmt_keys = None
        self.protect_existing_users = False
        print("management sheet id: {}".format(mgmt_sheet_id))

    def create_user(self, dashboard_tab_name, email_tab_name, domains_tab_name, forgiving):
        """ create an object of the format of the format....
        {
            "user_sheet_id": {
                "dashboard": dashboard_tab_name,
                "emails": email_tab_name,
                etc
            }
        }
        """
        usr_obj = {
            self.user_sheet_id: {
                "dashboard": dashboard_tab_name,
                "emails": email_tab_name,
                "domains": domains_tab_name,
                "forgiving": forgiving
            }
        }

        user_object_key = list(usr_obj.keys())
        internal_keys = list(usr_obj[self.user_sheet_id].keys())
        self.mgmt_keys = user_object_key + internal_keys

        return usr_obj

    def create_management_sheet(self, mgmt_tab_name):
        return self.create_sheet(mgmt_tab_name)

    def get_management_users(self):
        """ get the list of users from the management sheet, format if required and return """
        users = self.get_values(self.mgmt_tab_name)

        print("retrieved management sheet users: {}".format(users))
        # print("retrieved management sheet:", time.time() - st)

        users_dict = {}  # place outside "if" statement - required if no existing users

        if users:
            # if less than 4 items per row, add in spaces
            for site_row in users:
                if len(site_row) < len(self.mgmt_keys):
                    for number in range(len(self.mgmt_keys) - len(site_row)):  # if the row has missing items from the user object, add blank cells
                        site_row.append("")

            # convert to a list of objects
            for site_row in users:
                user_obj = {}
                id_key = site_row[0]
                user_obj[id_key] = {}
                user_obj[id_key]["dashboard"] = site_row[1]
                user_obj[id_key]["emails"] = site_row[2]
                user_obj[id_key]["domains"] = site_row[3]
                user_obj[id_key]["forgiving"] = site_row[4]
                users_dict.update(user_obj)

        print("consolidated management sheet users: {}".format(users_dict))
        return users_dict

    def update_management_users(self, this_usr_obj):
        """ update the user dictionary with the current object and return """
        try:
            users_dict = self.get_management_users()
            print("user dictionary retrieved {}".format(users_dict))
            if not users_dict:
                self.protect_existing_users = True
            users_dict.update(this_usr_obj)
            print("user dictionary after update of current user {}".format(users_dict))
            return users_dict
        except:
            print("failed to get or update users from the management sheet")
            return None

    def user_dict_to_list(self, users_dict):
        """ convert dict back to list so that it can be sent back to the sheet """
        print("management user dictionary for conversion to list {}".format(users_dict))
        user_value_list = []

        for id_key in users_dict:
            user_values = []
            user_values.append(id_key)
            user_values.append(users_dict[id_key]["dashboard"])
            user_values.append(users_dict[id_key]["emails"])
            user_values.append(users_dict[id_key]["domains"])
            user_values.append(users_dict[id_key]["forgiving"])

            user_value_list.append(user_values)

        # user_value_list = [bbc for key, value in users_dict]
        print("management user list converted from dictionary")
        return user_value_list

    def update_management_sheet(self, user_value_list):
        # self.clear_sheet(self.mgmt_tab_name)
        print("protect_existing_users: {}".format(self.protect_existing_users))
        if self.protect_existing_users:
            self.insert_values(self.mgmt_tab_name, user_value_list, append=True)
        else:
            self.clear_sheet(self.mgmt_tab_name)
            self.insert_values(self.mgmt_tab_name, user_value_list)
        # self.insert_values(self.mgmt_tab_name, user_value_list, overwrite)








class User(object):
    def __init__(self, userid, username=None):
        self.userid = userid
        self.username = username


class DefaultPlugin(object):
    def __init__(self):
        pass

    def find_user(self):
        """
        find user identified in current request
        returns None if no user can be identified
        """
        return User(userid="test", username="test")

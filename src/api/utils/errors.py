
class ApiError(Exception):
    def __init__(self, message, status=400, field=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field

    def to_dict(self):
        data = {"msg": self.message}
        if self.field:
            data["field"] = self.field
        return data

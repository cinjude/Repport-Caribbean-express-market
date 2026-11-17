
import inspect

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.theme import Bootstrap4Theme

import models
from extensions import db


class SafeModelView(ModelView):
    column_exclude_list = ("password_hash",)
    form_excluded_columns = ("password_hash",)


def setup_admin(app):
    if app.config.get("IS_PRODUCTION"):
        return

    admin = Admin(app, name="Caribbean Express · Dev Admin",
                  theme=Bootstrap4Theme(swatch="cerulean"))

    # Add every model exported by models/__init__.py
    for _name, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and issubclass(obj, db.Model):
            admin.add_view(SafeModelView(obj, db.session))

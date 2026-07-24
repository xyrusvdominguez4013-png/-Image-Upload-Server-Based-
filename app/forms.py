"""Flask-WTF forms. CSRF protection is applied automatically via the
CSRFProtect extension initialized in app/extensions.py.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SubmitField

ALLOWED_EXTENSIONS_LIST = ["jpg", "jpeg", "png", "gif", "webp"]


class ImageUploadForm(FlaskForm):
    image = FileField(
        "Image",
        validators=[
            FileRequired(message="Please choose an image to upload."),
            FileAllowed(
                ALLOWED_EXTENSIONS_LIST,
                message="Only JPG, JPEG, PNG, GIF, and WEBP files are allowed.",
            ),
        ],
    )
    submit = SubmitField("Upload")

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(127), unique=True)
    password = db.Column(db.String(31))
    name = db.Column(db.String(1023))
    has_voted = db.Column(db.Boolean, default=False)

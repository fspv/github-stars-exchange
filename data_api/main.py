import os

import werkzeug
from flask import (Flask, g, redirect, render_template_string, request,
                   session, url_for)
from flask_github import GitHub
from google.cloud import secretmanager

import models

app = Flask(__name__)

secretmanager_client = secretmanager.SecretManagerServiceClient()

app.config["DEBUG"] = True
app.config["GITHUB_CLIENT_ID"] = os.environ.get(
    "GITHUB_CLIENT_ID", None
) or secretmanager_client.access_secret_version(
    request={"name": "projects/288625958479/secrets/GITHUB_CLIENT_ID/versions/1"}
).payload.data.decode(
    "UTF-8"
)
app.config["GITHUB_CLIENT_SECRET"] = os.environ.get(
    "GITHUB_CLIENT_SECRET", None
) or secretmanager_client.access_secret_version(
    request={"name": "projects/288625958479/secrets/GITHUB_CLIENT_SECRET/versions/1"}
).payload.data.decode(
    "UTF-8"
)

# For GitHub Enterprise
# app.config["GITHUB_BASE_URL"] = "https://HOSTNAME/api/v3/"
# app.config["GITHUB_AUTH_URL"] = "https://HOSTNAME/login/oauth/"

github = GitHub(app)

db_session = models.create_database()


@app.before_request
def before_request():
    g.user = None
    if "user_id" in session:
        g.user = db_session.query(models.User).filter_by(session["user_id"]).first()


@app.after_request
def after_request(response):
    # db_session.remove()
    return response


@app.route("/")
def index():
    if g.user:
        t = (
            'Hello! %s <a href="{{ url_for("user") }}">Get user</a> '
            '<a href="{{ url_for("repo") }}">Get repo</a> '
            '<a href="{{ url_for("logout") }}">Logout</a>'
        )
        t %= g.user.github_login
    else:
        t = 'Hello! <a href="{{ url_for("login") }}">Login</a>'

    return render_template_string(t)


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.route("/auth/github")
def login() -> int:
    return github.authorize()


@app.route("/auth/github/callback")
@github.authorized_handler
def authorized(access_token: str) -> werkzeug.wrappers.response.Response:

    next_url = request.args.get("next") or url_for("index")
    if access_token is None:
        return redirect(next_url)

    user = (
        db_session.query(models.User)
        .filter_by(github_access_token=access_token)
        .first()
    )
    if user is None:
        user = models.User(github_access_token=access_token)
        db_session.add(user)

    user.github_access_token = access_token

    # Not necessary to get these details here
    # but it helps humans to identify users easily.
    g.user = user
    github_user = github.get("/user")
    user.github_id = github_user["id"]
    user.github_login = github_user["login"]

    db_session.commit()

    session["user_id"] = user.id
    return redirect(next_url)

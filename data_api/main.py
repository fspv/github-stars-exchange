import os
from typing import Optional

import flask
import werkzeug
from flask import (Flask, g, jsonify, redirect, render_template_string,
                   request, session, url_for)
from flask_github import GitHub  # type: ignore
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
app.config["POSTGRES_USER"] = secretmanager_client.access_secret_version(
    request={"name": "projects/288625958479/secrets/POSTGRES_USER/versions/1"}
).payload.data.decode("UTF-8")
app.config["POSTGRES_PASSWORD"] = secretmanager_client.access_secret_version(
    request={"name": "projects/288625958479/secrets/POSTGRES_PASSWORD/versions/2"}
).payload.data.decode("UTF-8")
app.config["POSTGRES_DATABASE"] = secretmanager_client.access_secret_version(
    request={"name": "projects/288625958479/secrets/POSTGRES_DATABASE/versions/2"}
).payload.data.decode("UTF-8")
app.config["POSTGRES_CONNECTION_NAME"] = secretmanager_client.access_secret_version(
    request={
        "name": "projects/288625958479/secrets/POSTGRES_CONNECTION_NAME/versions/1"
    }
).payload.data.decode("UTF-8")


app.secret_key = "slkfjldskjfdhfouie9382y3289989p32yfp9q32y97fge"
app.config["SESSION_TYPE"] = "filesystem"

# For GitHub Enterprise
# app.config["GITHUB_BASE_URL"] = "https://HOSTNAME/api/v3/"
# app.config["GITHUB_AUTH_URL"] = "https://HOSTNAME/login/oauth/"

github = GitHub(app)

db_engine = models.init_google_postgres_connection_engine(
    user=app.config["POSTGRES_USER"],
    password=app.config["POSTGRES_PASSWORD"],
    database=app.config["POSTGRES_DATABASE"],
    connection_name=app.config["POSTGRES_CONNECTION_NAME"],
)

db_session = models.create_database(db_engine)


@app.before_request
def before_request() -> None:
    g.user = None
    if "user_id" in session:
        g.user = db_session.query(models.User).filter_by(id=session["user_id"]).first()


@app.after_request
def after_request(response: flask.wrappers.Response) -> flask.wrappers.Response:
    # db_session.remove()
    return response


@app.route("/")
def index() -> str:
    if g.user:
        template = (
            'Hello! %s <a href="{{ url_for("user") }}">Get user</a> '
            '<a href="{{ url_for("repo") }}">Get repo</a> '
            '<a href="{{ url_for("logout") }}">Logout</a>'
        )
        template %= g.user.github_login
    else:
        template = 'Hello! <a href="{{ url_for("login") }}">Login</a>'

    return render_template_string(template)


@github.access_token_getter
def token_getter() -> Optional[str]:
    user = g.user
    if user is not None:
        return user.github_access_token

    return None


@app.route("/auth/github")
def login() -> werkzeug.wrappers.response.Response:
    return github.authorize()


@app.route("/logout")
def logout() -> werkzeug.wrappers.response.Response:
    session.pop("user_id", None)
    return redirect(url_for("index"))


@app.route("/user")
def user() -> werkzeug.wrappers.response.Response:
    return jsonify(github.get("/user"))


@app.route("/repo")
def repo() -> werkzeug.wrappers.response.Response:
    return jsonify(github.get("/repos/cenkalti/github-flask"))


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

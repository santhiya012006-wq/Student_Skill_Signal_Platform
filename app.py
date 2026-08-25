from flask import Flask, render_template, request
import requests
import sqlite3
import os
from datetime import datetime, timedelta, timezone


# -----------------------------
# APP CONFIGURATION
# -----------------------------
app = Flask(__name__)


# -----------------------------
# GITHUB API CONFIGURATION
# -----------------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Only prints True or False, never prints the actual token
print("GitHub token available:", bool(GITHUB_TOKEN))

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Student-Skill-Platform"
}

# Add token if available
if GITHUB_TOKEN:
    GITHUB_HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


# -----------------------------
# DATABASE CONFIGURATION
# -----------------------------
DATABASE = "students.db"


# -----------------------------
# DATABASE FUNCTIONS
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE,

            name TEXT,

            avatar TEXT,

            skill_index INTEGER,

            skill_level TEXT,

            total_commits INTEGER,

            activity_level TEXT
        )
    """)

    connection.commit()
    connection.close()


# Create database and table
create_database()


# -----------------------------
# HOME PAGE
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------
# ANALYZE GITHUB PROFILE
# -----------------------------
@app.route("/analyze", methods=["GET", "POST"])
def analyze():

    # Show Analyze page
    if request.method == "GET":
        return render_template("analyze.html")

    # -----------------------------
    # GET USERNAME
    # -----------------------------
    username = request.form.get("username", "").strip()

    if not username:
        return render_template(
            "analyze.html",
            error="Please enter a GitHub username."
        )

    try:

        # =============================
        # 1. FETCH GITHUB PROFILE
        # =============================
        github_url = f"https://api.github.com/users/{username}"

        response = requests.get(
            github_url,
            headers=GITHUB_HEADERS,
            timeout=10
        )

        # Username not found
        if response.status_code == 404:
            return render_template(
                "analyze.html",
                error="GitHub username not found."
            )

        # Rate limit or access problem
        if response.status_code == 403:

            remaining = response.headers.get(
                "X-RateLimit-Remaining",
                "Unknown"
            )

            return render_template(
                "analyze.html",
                error=(
                    "GitHub API access limit reached. "
                    f"Requests remaining: {remaining}"
                )
            )

        # Other API errors
        if response.status_code != 200:
            return render_template(
                "analyze.html",
                error=(
                    f"Unable to fetch GitHub profile. "
                    f"Error code: {response.status_code}"
                )
            )

        user_data = response.json()


        # =============================
        # 2. FETCH REPOSITORIES
        # =============================
        repos_url = (
            f"https://api.github.com/users/"
            f"{username}/repos"
        )

        repos_response = requests.get(
            repos_url,
            headers=GITHUB_HEADERS,
            params={
                "per_page": 100,
                "sort": "updated",
                "direction": "desc"
            },
            timeout=10
        )

        # Initialize safely
        repos_data = []

        if repos_response.status_code == 403:

            remaining = repos_response.headers.get(
                "X-RateLimit-Remaining",
                "Unknown"
            )

            return render_template(
                "analyze.html",
                error=(
                    "GitHub API access limit reached while "
                    f"fetching repositories. Requests remaining: "
                    f"{remaining}"
                )
            )

        elif repos_response.status_code == 200:
            repos_data = repos_response.json()

        else:
            repos_data = []


        # =============================
        # 3. FETCH PUBLIC EVENTS
        # =============================
        # This replaces making one commit API request
        # for every repository.
        events_url = (
            f"https://api.github.com/users/"
            f"{username}/events/public"
        )

        events_response = requests.get(
            events_url,
            headers=GITHUB_HEADERS,
            params={
                "per_page": 100
            },
            timeout=10
        )

        total_commits = 0

        thirty_days_ago = (
            datetime.now(timezone.utc)
            - timedelta(days=30)
        )

        # Analyze recent PushEvents
        if events_response.status_code == 200:

            events_data = events_response.json()

            for event in events_data:

                # Only count push events
                if event.get("type") != "PushEvent":
                    continue

                created_at = event.get("created_at")

                if not created_at:
                    continue

                try:

                    event_date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )

                    # Count only events from last 30 days
                    if event_date >= thirty_days_ago:

                        commits = (
                            event.get("payload", {})
                            .get("commits", [])
                        )

                        total_commits += len(commits)

                except (ValueError, TypeError):
                    continue


        # =============================
        # 4. ANALYZE REPOSITORIES
        # =============================
        repositories = []
        languages = []

        for repo in repos_data:

            repo_name = repo.get("name")

            # Skip invalid repositories
            if not repo_name:
                continue

            language = repo.get("language")

            repo_info = {

                "name": repo_name,

                "description": (
                    repo.get("description")
                    or "No description available."
                ),

                "language": (
                    language
                    or "Not specified"
                ),

                "stars": repo.get(
                    "stargazers_count",
                    0
                ),

                "forks": repo.get(
                    "forks_count",
                    0
                ),

                # Total user activity is calculated
                # through Events API
                "commits": 0,

                "url": repo.get("html_url")
            }

            repositories.append(repo_info)

            # Detect unique languages
            if language and language not in languages:
                languages.append(language)


        # =============================
        # 5. CALCULATE SKILL INDEX
        # =============================

        # Repository Score - Maximum 30
        repository_score = min(
            len(repositories) * 5,
            30
        )

        # Technology Score - Maximum 30
        technology_score = min(
            len(languages) * 5,
            30
        )

        # Star Score - Maximum 20
        total_stars = sum(
            repo.get("stars", 0)
            for repo in repositories
        )

        star_score = min(
            total_stars * 2,
            20
        )

        # Follower Score - Maximum 10
        follower_score = min(
            user_data.get("followers", 0),
            10
        )

        # Profile Completeness Score - Maximum 10
        profile_score = 0

        if user_data.get("name"):
            profile_score += 3

        if user_data.get("bio"):
            profile_score += 3

        if user_data.get("avatar_url"):
            profile_score += 2

        if user_data.get("html_url"):
            profile_score += 2


        # Final Skill Index - Maximum 100
        skill_index = (
            repository_score
            + technology_score
            + star_score
            + follower_score
            + profile_score
        )


        # =============================
        # 6. DETERMINE SKILL LEVEL
        # =============================
        if skill_index < 40:
            skill_level = "Beginner"

        elif skill_index < 70:
            skill_level = "Intermediate"

        elif skill_index < 90:
            skill_level = "Advanced"

        else:
            skill_level = "Expert"


        # =============================
        # 7. COMMIT ACTIVITY ANALYSIS
        # =============================
        if total_commits == 0:

            activity_score = 0
            activity_level = "Inactive"

        elif total_commits < 5:

            activity_score = 5
            activity_level = "Low Activity"

        elif total_commits < 10:

            activity_score = 10
            activity_level = "Moderately Active"

        elif total_commits < 20:

            activity_score = 15
            activity_level = "Active"

        else:

            activity_score = 20
            activity_level = "Highly Active"


        # =============================
        # 8. CREATE PROFILE DATA
        # =============================
        profile = {

            # Basic Profile
            "name": (
                user_data.get("name")
                or username
            ),

            "username": (
                user_data.get("login")
                or username
            ),

            "avatar": user_data.get("avatar_url"),

            "bio": (
                user_data.get("bio")
                or "No bio available."
            ),

            "public_repos": (
                user_data.get("public_repos", 0)
            ),

            "followers": (
                user_data.get("followers", 0)
            ),

            "following": (
                user_data.get("following", 0)
            ),

            "profile_url": (
                user_data.get("html_url")
            ),

            # Skill Index
            "skill_index": skill_index,
            "skill_level": skill_level,

            # Activity
            "total_commits": total_commits,
            "activity_score": activity_score,
            "activity_level": activity_level,

            # Score Breakdown
            "repository_score": repository_score,
            "technology_score": technology_score,
            "star_score": star_score,
            "follower_score": follower_score,
            "profile_score": profile_score
        }


        # =============================
        # 9. SAVE TO SQLITE DATABASE
        # =============================
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO students (

                username,
                name,
                avatar,
                skill_index,
                skill_level,
                total_commits,
                activity_level

            )

            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(username) DO UPDATE SET

                name = excluded.name,
                avatar = excluded.avatar,
                skill_index = excluded.skill_index,
                skill_level = excluded.skill_level,
                total_commits = excluded.total_commits,
                activity_level = excluded.activity_level
        """, (

            profile["username"],
            profile["name"],
            profile["avatar"],
            profile["skill_index"],
            profile["skill_level"],
            profile["total_commits"],
            profile["activity_level"]

        ))

        connection.commit()
        connection.close()


        # =============================
        # 10. SHOW RESULT PAGE
        # =============================
        return render_template(
            "result.html",
            profile=profile,
            repositories=repositories,
            languages=languages
        )


    # =============================
    # ERROR HANDLING
    # =============================
    except requests.Timeout:

        return render_template(
            "analyze.html",
            error="Request timed out. Please try again."
        )


    except requests.RequestException:

        return render_template(
            "analyze.html",
            error=(
                "Network error. Please check your "
                "internet connection and try again."
            )
        )


    except Exception as e:

        print("UNEXPECTED ERROR:", str(e))

        return render_template(
            "analyze.html",
            error=f"Unexpected error: {str(e)}"
        )


# -----------------------------
# LEADERBOARD PAGE
# -----------------------------
@app.route("/leaderboard")
def leaderboard():

    connection = get_db_connection()

    students = connection.execute("""

        SELECT *

        FROM students

        ORDER BY skill_index DESC,
                 total_commits DESC

    """).fetchall()

    connection.close()

    return render_template(
        "leaderboard.html",
        students=students
    )


# -----------------------------
# RUN APPLICATION
# -----------------------------
if __name__ == "__main__":
    app.run(
        debug=True
    )
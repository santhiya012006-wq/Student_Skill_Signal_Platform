# Student Skill Signal Platform

A web-based platform that analyzes a student's GitHub profile and repositories to identify programming skills, project experience, coding activity, and overall technical capability.

## Features

- GitHub profile analysis
- Public repository analysis
- Programming language detection
- Repository quality scoring
- Student Skill Index calculation
- Skill level classification
- Commit activity analysis
- Visual analytics dashboard
- Student leaderboard
- SQLite database integration

## Student Skill Index

The Student Skill Index is calculated out of 100 based on different GitHub profile factors.

| Category | Maximum Score |
|---|---:|
| Repository Quality | 30 |
| Technology Stack | 30 |
| GitHub Engagement | 20 |
| GitHub Presence | 10 |
| Profile Completeness | 10 |
| **Total** | **100** |

## Skill Levels

| Score | Level |
|---|---|
| 0–39 | Beginner |
| 40–69 | Intermediate |
| 70–89 | Advanced |
| 90–100 | Expert |

## Technology Stack

- Python
- Flask
- HTML
- CSS
- JavaScript
- GitHub REST API
- Chart.js
- SQLite

## Project Structure

```text
Student_Skill_Signal_Platform/
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
├── templates/
│   ├── index.html
│   ├── analyze.html
│   ├── result.html
│   └── leaderboard.html
│
├── app.py
├── .gitignore
├── README.md
└── students.db
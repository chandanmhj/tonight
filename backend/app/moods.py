"""Moods describe the kind of film someone wants tonight; genres are TMDB's own genre names.

MOODS keys must match frontend/src/moods.js, and GENRES must match frontend/src/genres.js.
Each mood maps to TMDB genres, and every movie is tagged with the moods its genres fit.
A simple start: for better tags later, have the LLM label each movie once and store the
result in movies.mood_tags.
"""
MOODS = {
    "funny":        {"genres": {"Comedy", "Family", "Animation"},
                     "hint": "light, funny and easy to watch"},
    "emotional":    {"genres": {"Drama", "Music", "History"},
                     "hint": "emotional, moving and character driven"},
    "thrilling":    {"genres": {"Thriller", "Crime", "Horror", "Action", "Mystery"},
                     "hint": "tense, gripping and fast paced"},
    "mind-bending": {"genres": {"Science Fiction", "Mystery", "Thriller"},
                     "hint": "clever, twisty and thought provoking"},
    "adventurous":  {"genres": {"Adventure", "Action", "Fantasy", "Western"},
                     "hint": "big, exciting and escapist"},
    "romantic":     {"genres": {"Romance"},
                     "hint": "romantic and warm"},
}

GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family",
    "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", "Science Fiction",
    "Thriller", "War", "Western",
]


def tags_for(genres):
    g = set(genres)
    return [name for name, m in MOODS.items() if g & m["genres"]]

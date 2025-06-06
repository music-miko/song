from pymongo import MongoClient


client = MongoClient("mongodb+srv://songcounts:cWjZPk0lFdWJ6tXj@music.atn13th.mongodb.net/?retryWrites=true&w=majority&appName=music")
db = client["music"]
collection = db["song"]

def is_song_sent(video_id: str) -> bool:
    return collection.find_one({"video_id": video_id}) is not None

def mark_song_as_sent(video_id: str):
    collection.insert_one({"video_id": video_id})

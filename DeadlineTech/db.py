from pymongo import MongoClient


client = MongoClient("mongodb+srv://songcounts:cWjZPk0lFdWJ6tXj@music.atn13th.mongodb.net/?retryWrites=true&w=majority&appName=music")
db = client["music"]
collection = db["song"]

def is_song_sent(video_id: str) -> bool:
    return collection.find_one({"video_id": video_id}) is not None

# Save song with file_id
def mark_song_as_sent(video_id: str, file_id: str):
    songs_collection.update_one(
        {"video_id": video_id},
        {"$set": {"file_id": file_id}},
        upsert=True
    )

# Check if song exists and get file_id
def get_saved_file_id(video_id: str) -> str | None:
    result = songs_collection.find_one({"video_id": video_id})
    return result["file_id"] if result else None

# Optional: Clear cache (if needed)
def clear_all_cached_songs():
    songs_collection.delete_many({})

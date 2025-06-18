# ==========================================================
# 🔒 All Rights Reserved © Team DeadlineTech
# 📁 This file is part of the DeadlineTech Project.
# ==========================================================


from pyrogram import filters
from pyrogram.types import Message
from DeadlineTech import app
from DeadlineTech.core.mongo import mongodb

deadline = mongodb.deadline  # Access the collection

@app.on_message(filters.command("del_assistants") & filters.user(6848223695)) 
async def delete_assistants_folder(client, message: Message):
    result = await deadline.delete_one({"assistants": {"$exists": True}})
    
    if result.deleted_count == 0:
        await message.reply_text("❌ No 'assistants' folder found in the collection.")
    else:
        await message.reply_text("✅ 'assistants' folder has been deleted from the collection.")


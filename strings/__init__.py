import os
import yaml

languages = {}
languages_present = {}


def get_string(lang: str):
    return languages.get(lang, languages.get("en", {}))


# Load base English file first
if "en" not in languages:
    try:
        with open("./strings/langs/en.yml", encoding="utf-8") as f:
            languages["en"] = yaml.safe_load(f)
            languages_present["en"] = languages["en"]["name"]
            print(f"✅ Loaded base language: {languages_present['en']}")
    except Exception as e:
        print(f"❌ Error loading en.yml: {e}")
        exit()

# Load other languages
for filename in os.listdir("./strings/langs/"):
    if filename.endswith(".yml"):
        language_name = filename[:-4]
        if language_name == "en":
            continue
        try:
            with open(f"./strings/langs/{filename}", encoding="utf-8") as f:
                lang_data = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
            continue

        # Merge missing keys from English
        for item in languages["en"]:
            if item not in lang_data:
                lang_data[item] = languages["en"][item]

        languages[language_name] = lang_data
        try:
            languages_present[language_name] = lang_data["name"]
            print(f"✅ Loaded language: {languages_present[language_name]} ({language_name})")
        except KeyError:
            print(f"⚠️ Missing 'name' key in {filename}")
        except Exception as e:
            print(f"❌ Unexpected error in {filename}: {e}")
            exit()

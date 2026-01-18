import os
import zipfile
import concurrent.futures
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# --- CONFIGURATION ---
load_dotenv()

CATEGORIES = ["Lecture", "Lab", "Tutorial", "Misc"]
MAX_WORKERS = 10 

client = OpenAI()

# --- AI FUNCTION ---

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5), reraise=True)
def call_openai_with_retry(system_instruction, user_prompt):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
    )
    return completion.choices[0].message.content.strip().title()

def get_category_from_ai(file_path_str):
    """
    Sends the path to OpenAI to determine the category.
    """
    system_instruction = "You are a helpful file organization assistant."
    user_prompt = f"""
Classify the following file path into exactly one of these categories: 
{', '.join(CATEGORIES)}.

Path: "{file_path_str}"

Context:
- Lecture: Slides, theory, chapters, week numbers usually imply lectures.
- Lab: Code, practicals, experiments, 'practical'.
- Tutorial: Problem sets, exercises, sheets, homework.
- Misc: Syllabus, schedules, admin docs.

Reply ONLY with the category name. No punctuation.
    """
    try:
        category = call_openai_with_retry(system_instruction, user_prompt)
        return category if category in CATEGORIES else "Misc"
    except Exception as e:
        print(f"⚠️ FAILED after retries for '{file_path_str}': {e}")
        return "Misc"

# --- MAIN LOGIC ---

def categorize_zip_content(zip_file_path):
    """
    Reads a zip file (without extracting), categorizes PDFs via AI, 
    and returns a dictionary of lists.
    """
    # Initialize Dictionary
    categorized_files = {cat: [] for cat in CATEGORIES}

    if not os.path.exists(zip_file_path):
        print(f"❌ Error: File '{zip_file_path}' not found.")
        return categorized_files

    print(f"📂 Reading content of '{zip_file_path}' (No extraction)...")
    
    try:
        # 1. Read the Zip Table of Contents
        pdf_paths = []
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            # Get list of all files inside the zip
            all_files = zip_ref.namelist()
            
            # Filter for PDFs (ignoring Mac OS hidden files)
            for file in all_files:
                if file.lower().endswith(".pdf") and "__MACOSX" not in file:
                    pdf_paths.append(file)

            # Unzip the file and place contents in the same directory
            # This is a temporary solution since it's more convenient this way
            # You need to assume zip_file_path is in a temporary directory
            zip_ref.extractall(zip_file_path.parent)

        total_files = len(pdf_paths)
        if total_files == 0:
            print("No PDF files found inside the zip.")
            return categorized_files

        print(f"🚀 Categorizing {total_files} paths using AI...")

        # 2. Parallel Processing (Just asking AI, no moving files)
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # We map the future to the original path so we know which file it was
            future_to_path = {
                executor.submit(get_category_from_ai, path): path 
                for path in pdf_paths
            }
            
            for future in concurrent.futures.as_completed(future_to_path):
                original_path = future_to_path[future]
                try:
                    category = future.result()
                    categorized_files[category].append(original_path)
                    print(f"  -> [{category}] {original_path}")
                except Exception as exc:
                    print(f"❌ Error processing {original_path}: {exc}")

    except zipfile.BadZipFile:
        print("❌ Error: The file is not a valid zip file.")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
            
    return categorized_files

# --- EXECUTION ---

if __name__ == "__main__":
    my_zip = "CS4261.zip"
    
    # Run the function
    results = categorize_zip_content(my_zip)
    
    # Print Result
    print("\n" + "="*40)
    print("📊 FINAL CATEGORIZATION REPORT")
    print("="*40)
    
    import json
    # Print nicely formatted JSON
    print(json.dumps(results, indent=2))
import os
import shutil

# ----------------------------------------------
# LIST OF FOLDERS TO DELETE COMPLETELY
# ----------------------------------------------
FOLDERS_TO_DELETE = [
    "recommender/ml_engine",
    "recommender/ai",
    "recommender/engines",
    "recommender/utils",
]

# ----------------------------------------------
# LIST OF FILES TO DELETE
# ----------------------------------------------
FILES_TO_DELETE = [
    "03_generate_recommendations.py",
    "03_predict_recommendations.py",
    "04_predict_recommendations.py",
    "04_train_recommender.py",
    "04_train_retrieval_model.py",
    "05_generate_recommendations_api.py",
    "05_generate_recommendations_csv.py",
    "05_recommend_api.py",
    "check_model.py",
    "evaluate_model.py",
    "export_training_csv.py",
    "import_recommendations.py",
    "inspect_model.py",
    "model_inference.py",
    "model_preprocessing.py",
    "pest_recommender_prepare.py",
    "pest_recommender_train.py",
    "populate_ratings.py",
    "populate_recommendations.py",
    "predict_api.py",
    "prepare_training_dataset.py",
    "product_embeddings.py",
    "product_search.py",
    "recommend.py",
    "train_model_cf.py",
    "train_model_from_csv.py",
    "train_recommender.py",
    "train_model.py",
    "train.py",
]

def delete_folder(path):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
        print(f"✅ Deleted folder: {path}")
    else:
        print(f"⚠️ Folder not found: {path}")

def delete_file(path):
    if os.path.exists(path):
        os.remove(path)
        print(f"🗑️ Deleted file: {path}")
    else:
        print(f"⚠️ File not found: {path}")

def main():
    print("============================================")
    print("🧹 Cleaning Recommender Project Structure...")
    print("============================================")

    # Delete folders
    for folder in FOLDERS_TO_DELETE:
        delete_folder(folder)

    # Delete files
    for file in FILES_TO_DELETE:
        delete_file(file)

    print("\n🎉 CLEANUP COMPLETE — Project is now clean & organized.")

if __name__ == "__main__":
    main()

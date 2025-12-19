import pandas as pd
import numpy as np
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ================================================================
# 1. LOAD DATA
# ================================================================
PURCHASE_FILE = "final_ml_training.csv"          # customer_id, product_name
PRODUCT_FILE = "master_products.csv"             # product_name, category, description

df = pd.read_csv(PURCHASE_FILE)
products = pd.read_csv(PRODUCT_FILE)

# Merge product metadata with purchases
df = df.merge(products, on="product_name", how="left")


# ================================================================
# 2. BUILD USER–ITEM MATRIX (Collaborative Filtering)
# ================================================================
pivot = df.pivot_table(
    index="customer_id",
    columns="product_name",
    values="quantity",
    aggfunc="sum",
    fill_value=0
)

pivot_matrix = pivot.values
cf_similarity = cosine_similarity(pivot_matrix)


# ================================================================
# 3. CONTENT-BASED RECOMMENDER (TF-IDF)
# ================================================================
# Combine product fields
products["combined"] = (
    products["product_name"].fillna("") + " " +
    products["category"].fillna("") + " " +
    products["description"].fillna("")
)

tfidf = TfidfVectorizer(stop_words="english")
tfidf_matrix = tfidf.fit_transform(products["combined"])

content_similarity = cosine_similarity(tfidf_matrix)


# ================================================================
# 4. MAP PRODUCT INDEXES
# ================================================================
product_list = products["product_name"].tolist()
product_to_index = {p: i for i, p in enumerate(product_list)}


# ================================================================
# 5. HYBRID PREDICTION FUNCTION
# ================================================================
def hybrid_recommend(customer_id, top_n=10):
    if customer_id not in pivot.index:
        # Pure content fallback for new customers
        return products["product_name"].head(top_n).tolist()

    customer_idx = pivot.index.tolist().index(customer_id)

    # CF scores
    cf_scores = cf_similarity[customer_idx]

    # Products user already bought
    purchased = set(pivot.columns[pivot.iloc[customer_idx] > 0])

    hybrid_scores = {}

    for product in product_list:
        p_idx = product_to_index[product]

        # content-based score — mean similarity with purchased products
        if purchased:
            sim_list = []
            for bought_item in purchased:
                if bought_item in product_to_index:
                    b_idx = product_to_index[bought_item]
                    sim_list.append(content_similarity[p_idx][b_idx])

            content_score = np.mean(sim_list) if sim_list else 0
        else:
            content_score = 0

        # CF score — user's CF vector doesn't give product score directly,
        # so simple fallback based on popularity (sum)
        cf_score = pivot[product].sum()

        # hybrid
        final_score = 0.7 * cf_score + 0.3 * content_score
        hybrid_scores[product] = final_score

    # Remove purchased items
    for p in purchased:
        hybrid_scores.pop(p, None)

    # Sort
    sorted_products = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)

    return [p for p, s in sorted_products[:top_n]]


# ================================================================
# 6. SAVE MODEL
# ================================================================
MODEL = {
    "pivot": pivot,
    "cf_similarity": cf_similarity,
    "products": products,
    "product_to_index": product_to_index,
    "content_similarity": content_similarity,
    "hybrid_recommend": hybrid_recommend
}

with open("hybrid_recommender.pkl", "wb") as f:
    pickle.dump(MODEL, f)

print("✅ Hybrid model trained & saved as hybrid_recommender.pkl")

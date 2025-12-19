# recommender/recommender_engine.py
import os
import pickle
import numpy as np
import pandas as pd
from django.db import models
from django.db.models import Count



from django.db import connection
from sklearn.metrics.pairwise import cosine_similarity

from recommender.models import Rating, Item, SavedModel, PestRecommendation

from crmapp.models import (
    Product,
    customer_details,
    TaxInvoice,
    TaxInvoiceItem,
    ServiceProduct,
    PurchaseHistory

)



# ------------------------
# Paths
# ------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAINED_MODELS_DIR = os.path.join(BASE_DIR, "..", "trained_models")
os.makedirs(TRAINED_MODELS_DIR, exist_ok=True)

USER_ITEM_MATRIX = os.path.join(TRAINED_MODELS_DIR, "user_item_matrix.csv")
ITEM_SIM_MODEL = os.path.join(TRAINED_MODELS_DIR, "item_similarity_model.pkl")
USER_TOP5 = os.path.join(TRAINED_MODELS_DIR, "user_top5_recommendations.csv")


# ------------------------
# Fabricated helpers
# ------------------------
def load_fabricated_models():
    """Load fabricated CSVs / pickles if present (optional helper)."""
    user_item_df = None
    item_sim = None
    rec_df = None

    try:
        if os.path.exists(USER_ITEM_MATRIX):
            try:
                user_item_df = pd.read_csv(USER_ITEM_MATRIX, index_col=0)
            except Exception as e:
                print("⚠️ Could not read USER_ITEM_MATRIX as CSV:", e)

        if os.path.exists(ITEM_SIM_MODEL):
            # ITEM_SIM_MODEL may be a pickle (preferred) or CSV — try pickle first
            try:
                with open(ITEM_SIM_MODEL, "rb") as f:
                    item_sim = pickle.load(f)
                    # if it's numpy array, convert to DataFrame with default index/cols (caller must handle mapping)
                    if isinstance(item_sim, np.ndarray):
                        item_sim = pd.DataFrame(item_sim)
            except Exception:
                try:
                    # fallback try reading as csv
                    item_sim = pd.read_csv(ITEM_SIM_MODEL, index_col=0)
                except Exception as e:
                    print("⚠️ Could not load ITEM_SIM_MODEL:", e)
                    item_sim = None

        if os.path.exists(USER_TOP5):
            try:
                rec_df = pd.read_csv(USER_TOP5, index_col=0)
            except Exception as e:
                print("⚠️ Could not read USER_TOP5:", e)
                rec_df = None

        return user_item_df, item_sim, rec_df
    except Exception as e:
        print("⚠️ Error loading fabricated models:", e)
        return None, None, None

 
def get_fabricated_recommendations(customer_id, top_n=5):
    """
    Return fabricated top-n recommendations as:
        [{ "product_id": <id>, "score": <float> }, ...]
    Works whether DF index is int or str.
    """
    import pandas as pd

    _, _, rec_df = load_fabricated_models()
    if rec_df is None or rec_df.empty:
        return []

    # Convert id to string for matching
    cid_str = str(customer_id)

    # -----------------------------------------
    # 1️⃣ Check if index contains string version
    # -----------------------------------------
    if cid_str in rec_df.index:
        row = rec_df.loc[cid_str].dropna().tolist()
        return _normalize_rec_items(row, top_n)

    # -----------------------------------------
    # 2️⃣ Check int index match
    # -----------------------------------------
    if customer_id in rec_df.index:
        row = rec_df.loc[customer_id].dropna().tolist()
        return _normalize_rec_items(row, top_n)

    # -----------------------------------------
    # 3️⃣ Fallback → most frequent recommended items across all users
    # -----------------------------------------
    try:
        melted = rec_df.melt(value_name="product").dropna(subset=["product"])
        top = melted["product"].value_counts().head(top_n).index.tolist()
        return _normalize_rec_items(top, top_n)
    except Exception:
        return []


def _normalize_rec_items(items, top_n):
    """
    Normalize recommendation items into a clean standard format:

        { 
            "product_id": <int>, 
            "score": <float> 
        }

    Accepts any of these formats:
        - raw product_id (int/str)
        - dict: {"product_id": 10, "score": 0.9}
        - dict: {"id": 10}
        - fabricated CSV values (strings)
    """

    normalized = []

    for v in items[:top_n]:

        # ------------------------------
        # If already dict (recommended)
        # ------------------------------
        if isinstance(v, dict):
            pid = v.get("product_id") or v.get("id")
            score = float(v.get("score", 1.0))

        # ------------------------------
        # If value is raw product id
        # ------------------------------
        else:
            pid = v
            score = 1.0

        # ------------------------------
        # Convert to integer if possible
        # ------------------------------
        try:
            pid = int(pid)
        except:
            pass

        normalized.append({
            "product_id": pid,
            "score": score
        })

    return normalized


# ------------------------
# Trained model loader
# ------------------------
def load_trained_model(model_name="recommender_similarity"):
    """
    Loads a saved similarity matrix (pickled DataFrame or numpy array).
    The SavedModel table (recommender.SavedModel) stores file_path.
    """
    try:
        saved_model = SavedModel.objects.filter(name=model_name).latest("created_at")
        model_path = saved_model.file_path
        with open(model_path, "rb") as f:
            model_obj = pickle.load(f)
        # Accept pandas.DataFrame or numpy array.
        if isinstance(model_obj, pd.DataFrame):
            return model_obj
        else:
            # if numpy array, convert to DataFrame with no index (caller must know mapping)
            return pd.DataFrame(model_obj)
    except SavedModel.DoesNotExist:
        print("⚠️ No trained model saved (SavedModel row missing).")
        return None
    except Exception as e:
        print("⚠️ Error loading saved model:", e)
        return None


# -----------------------------------------------------------
# Generate Recommendations for a Customer
# -----------------------------------------------------------  

# -----------------------------------------------------------
# FINAL HYBRID AGGREGATOR (fixed to consume dicts)
# -----------------------------------------------------------
def generate_recommendations_for_user(customer_id, top_n=5):
    """
    Hybrid Recommendation Engine
    Weights:
        - Content-Based:      0.4
        - User-Based CF:      0.3
        - Cross-Sell:         0.2
        - Upsell:             0.1

    Returns: list of Product instances with .score attribute (float)
    """
    try:
        hybrid_results = {}  # pid -> score

        # 1) Fetch purchase history
        purchase_qs = PurchaseHistory.objects.filter(customer_id=customer_id)
        last_product = None
        if purchase_qs.exists():
            last = purchase_qs.order_by("-purchased_at").first()
            last_product = last.product if last else None

        # A. Content-based (0.4)
        if last_product:
            cb = get_content_based_recommendations(last_product.product_name, top_n=10)
            for rec in cb:
                pid = int(rec["product_id"])
                score = float(rec.get("score", 1.0) or 1.0)
                hybrid_results[pid] = hybrid_results.get(pid, 0.0) + 0.4 * score

        # B. User-based (0.3)
        ub = get_user_based_recommendations(customer_id, top_n=10)
        for rec in ub:
            pid = int(rec["product_id"])
            score = float(rec.get("score", 1.0) or 1.0)
            hybrid_results[pid] = hybrid_results.get(pid, 0.0) + 0.3 * score

        # C. Cross-sell (0.2)
        if last_product:
            cs = get_crosssell_recommendations(last_product.product_id, top_n=10)
        else:
            cs = get_crosssell_recommendations(customer_id, top_n=10)  # fallback still returns reasonable list
        for rec in cs:
            pid = int(rec["product_id"])
            score = float(rec.get("score", 1.0) or 1.0)
            hybrid_results[pid] = hybrid_results.get(pid, 0.0) + 0.2 * score

        # D. Upsell (0.1)
        if last_product:
            ups = get_upsell_recommendations(last_product.product_id, top_n=10)
            for rec in ups:
                pid = int(rec["product_id"])
                score = float(rec.get("score", 1.0) or 1.0)
                hybrid_results[pid] = hybrid_results.get(pid, 0.0) + 0.1 * score

        # If nothing produced, try fabricated
        if not hybrid_results:
            fab = get_fabricated_recommendations(customer_id, top_n)
            for rec in fab:
                pid = int(rec["product_id"])
                hybrid_results[pid] = hybrid_results.get(pid, 0.0) + (rec.get("score") or 1.0)

        # Final ranking
        ranked = sorted(hybrid_results.items(), key=lambda x: x[1], reverse=True)[:top_n]
        results = []
        for pid, sc in ranked:
            prod = Product.objects.filter(product_id=pid).first()
            if not prod:
                # try Item model if Product missing
                it = Item.objects.filter(product_id=pid).first()
                if it:
                    # wrap item into minimal Product-like object by using Product lookup if possible
                    # but prefer returning Product instances; skip otherwise
                    continue
                else:
                    continue
            prod.score = round(float(sc), 4)
            results.append(prod)

        # Save to DB (best-effort)
        try:
            save_recommendations_to_db(customer_id, results)
        except Exception as e:
            print("Could not save recommendations:", e)

        return results

    except Exception as e:
        print("❌ Error in generate_recommendations_for_user:", e)
        # fallback to purchase-history
        try:
            fh = get_purchase_history_signal(customer_id, top_n)
            # convert dicts to Product objects where possible
            out = []
            for rec in fh:
                pid = rec.get("product_id")
                prod = Product.objects.filter(product_id=pid).first()
                if prod:
                    prod.score = rec.get("score", 0)
                    out.append(prod)
            return out
        except Exception:
            return []
# =========================================================
# 8️⃣ SAVE RESULTS INTO pest_recommendations
# ========================================================= 

# -----------------------------------------------------------
# Save results into PestRecommendation table (recommended_product must be a Product instance)
# -----------------------------------------------------------
def save_recommendations_to_db(customer_id, products):
    """
    products: list of Product instances (with optional .score attribute)
    """
    try:
        PestRecommendation.objects.filter(customer_id=customer_id).delete()
    except Exception:
        pass

    for p in products:
        try:
            conf = getattr(p, "score", None) or 0.0
            # If 'p' is dict instead of Product, handle that
            if isinstance(p, dict):
                prod = Product.objects.filter(product_id=int(p.get("product_id"))).first()
                recommended_prod = prod
                conf = float(p.get("score", conf))
            else:
                recommended_prod = p

            if not recommended_prod:
                continue

            PestRecommendation.objects.create(
                customer_id=customer_id,
                base_product_id=None,
                recommended_product=recommended_prod,
                recommendation_type="hybrid",
                confidence_score=conf
            )
        except Exception as e:
            print("save_recommendations_to_db error:", e)
            continue



# -----------------------------------------------------------
# Fallback using PurchaseHistory
# -----------------------------------------------------------
def fallback_using_purchase_history(customer_id, top_n=5):
    """
    If no ratings exist — use products bought by similar customers.
    """

    # What customer bought
    user_purchases = list(
        PurchaseHistory.objects
        .filter(customer_id=customer_id)
        .values_list("product_id", flat=True)
    )

    # If no purchase history → Popular fallback
    if not user_purchases:
        return fallback_popularity(top_n)

    # Find other customers who bought same products
    similar_customers = (
        PurchaseHistory.objects
        .filter(product_id__in=user_purchases)
        .exclude(customer_id=customer_id)
        .values("customer_id")
        .annotate(cnt=Count("product_id"))
        .order_by("-cnt")
    )

    if not similar_customers:
        return fallback_popularity(top_n)

    similar_ids = [c["customer_id"] for c in similar_customers]

    # Products they bought
    also_bought = (
        PurchaseHistory.objects
        .filter(customer_id__in=similar_ids)
        .exclude(product_id__in=user_purchases)
        .values("product_id")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    product_ids = [x["product_id"] for x in also_bought]

    items = Item.objects.filter(product_id__in=product_ids)

    for item in items:
        item.score = None

    return items

# -----------------------------------------------------------
# POPULARITY FALLBACK
# -----------------------------------------------------------
def fallback_popularity(top_n=5):
    """
    Default fallback → popular products (based on frequency in PurchaseHistory).
    """

    top_products = (
        PurchaseHistory.objects
        .values("product_id")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    product_ids = [p["product_id"] for p in top_products]

    items = Item.objects.filter(product_id__in=product_ids)

    for item in items:
        item.score = None

    return items



# ---------------------------------------------------------
# 1️⃣ PURCHASE HISTORY – CUSTOMER → PRODUCTS
# ---------------------------------------------------------
def get_customer_purchase_history(customer_id):
    """Return list of product IDs purchased by customer."""
    invoice_items = (
        TaxInvoiceItem.objects
        .filter(tax_invoice__customer_id=customer_id)
        .values_list("product_name", flat=True)
    )

    # Match product_name → Product table
    product_ids = Product.objects.filter(
        product_name__in=list(invoice_items)
    ).values_list("product_id", flat=True)

    return list(product_ids)


# ---------------------------------------------------------
# 2️⃣ PRODUCT → CUSTOMERS WHO BOUGHT IT (for collaborative)
# ---------------------------------------------------------
def get_customers_who_bought_product(product_id):
    product = Product.objects.filter(product_id=product_id).first()
    if not product:
        return []

    return list(
        TaxInvoiceItem.objects
        .filter(product_name=product.product_name)
        .values_list("tax_invoice__customer_id", flat=True)
    )



# ---------------------------------------------------------------------
# ✅ Content-Based Filtering using PestRecommendation table
# --------------------------------------------------------------------- 
def get_content_based_recommendations(product_name, top_n=5):
    """
    Fetches ML-generated pest-based recommendations.
    This uses:
        - PestRecommendation.base_product → main product
        - PestRecommendation.recommended_product → recommended product
    """

    qs = (
        PestRecommendation.objects
        .filter(base_product__product_name__icontains=product_name)
        .order_by("-confidence_score")
        .values(
            "recommended_product__product_id",
            "recommended_product__product_name",
            "base_product__product_name",
            "confidence_score"
        )[:top_n]
    )

    results = [
        {
            "product_id": row["recommended_product__product_id"],
            "product_name": row["recommended_product__product_name"],
            "base_product": row["base_product__product_name"],
            "confidence": float(row["confidence_score"]),
        }
        for row in qs
    ]

    return results


 
# ---------------------------------------------------------------------
# ✅ Collaborative Filtering (Customers who bought X also bought Y)
# --------------------------------------------------------------------- 
from django.db.models import Count

def get_collaborative_recommendations(product_id, top_n=5):
    """
    Collaborative Filtering (Product → Product)
    Finds: Customers who bought X also bought Y
    """

    # Step 1: customers who bought the product
    customers = PurchaseHistory.objects.filter(
        product_id=product_id
    ).values_list("customer_id", flat=True)

    if not customers:
        return []

    # Step 2: products purchased by those customers
    qs = (
        PurchaseHistory.objects
        .filter(customer_id__in=customers)
        .exclude(product_id=product_id)
        .values("product_id", "product__product_name")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    return [
        {
            "product_id": row["product_id"],
            "product_name": row["product__product_name"],
            "score": row["freq"]
        }
        for row in qs
    ]

from crmapp.models import Product, ServiceProduct
from django.db.models import Avg


# ---------------------------------------------------------------------
# ✅ Upsell Recommendations (higher price / premium versions)
# ---------------------------------------------------------------------  
# from django.db.models import Avg, Count
from django.db.models.functions import Coalesce

from django.db.models import Avg, Count, DecimalField
from django.db.models.functions import Coalesce

def get_upsell_recommendations(product_id, top_n=5):
    """
    Upsell logic:
    1. Higher-priced products in same category
    2. Same-category alternatives
    3. Global best sellers
    """

    try:
        base = Product.objects.get(product_id=product_id)
    except Product.DoesNotExist:
        return []

    # 1️⃣ Base product price
    base_price = (
        ServiceProduct.objects
        .filter(product_id=product_id)
        .aggregate(
            avg_price=Coalesce(
                Avg("price"),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )["avg_price"]
    )

    # 2️⃣ Higher priced upsell options
    higher_priced = (
        Product.objects
        .filter(category=base.category)
        .exclude(product_id=product_id)
        .annotate(
            avg_price=Coalesce(
                Avg("serviceproduct__price"),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        .filter(avg_price__gt=base_price)
        .order_by("avg_price")
    )

    if higher_priced.exists():
        return [
            {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "average_price": float(p.avg_price),
                "reason": "Higher priced alternative"
            }
            for p in higher_priced[:top_n]
        ]

    # 3️⃣ Same category fallback
    same_category = (
        Product.objects
        .filter(category=base.category)
        .exclude(product_id=product_id)
        .annotate(
            avg_price=Coalesce(
                Avg("serviceproduct__price"),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
    )

    if same_category.exists():
        return [
            {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "average_price": float(p.avg_price),
                "reason": "Same category alternative"
            }
            for p in same_category[:top_n]
        ]

    # 4️⃣ Popular products fallback
    popular = (
        Product.objects
        .annotate(sales=Count("purchasehistory"))
        .order_by("-sales")[:top_n]
    )

    return [
        {
            "product_id": p.product_id,
            "product_name": p.product_name,
            "average_price": None,
            "reason": "Popular product"
        }
        for p in popular
    ]

# ✅ Cross-Sell Recommendations ("Frequently bought together")
# --------------------------------------------------------------------- 
# ---------------------------------------------------------------------
# ✅ Cross-Sell Recommendations ("What this customer may buy next")
# ------------------------------------------------------------------
from django.db.models import Count

def get_crosssell_recommendations(customer_id, top_n=5):
    """
    Cross-sell Recommendations:
    1) If customer has purchase history → frequently bought together
    2) If no purchase history → return best-selling products (fallback)
    """

    # STEP 1: Customer purchased products
    purchased = PurchaseHistory.objects.filter(
        customer_id=customer_id
    ).values_list("product_id", flat=True)

    # CASE A: No purchase history → Fallback to top sellers
    if not purchased:
        fallback = (
            PurchaseHistory.objects.values(
                "product_id", 
                "product__product_name",
                "product__category"
            )
            .annotate(total=Count("product_id"))
            .order_by("-total")[:top_n]
        )

        return [
            {
                "product_id": row["product_id"],
                "product_name": row["product__product_name"],
                "category": row["product__category"],
                "score": row["total"],
                "reason": "Popular product (customer has no purchase history)"
            }
            for row in fallback
        ]

    # CASE B: Customer has purchase history → Cross-sell
    customers = PurchaseHistory.objects.filter(
        product_id__in=purchased
    ).values_list("customer_id", flat=True)

    if not customers:
        return []

    qs = (
        PurchaseHistory.objects
        .filter(customer_id__in=customers)
        .exclude(product_id__in=purchased)
        .values(
            "product_id", 
            "product__product_name",
            "product__category"
        )
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    return [
        {
            "product_id": row["product_id"],
            "product_name": row["product__product_name"],
            "category": row["product__category"],
            "score": row["freq"],
            "reason": "Frequently bought together"
        }
        for row in qs
    ]
# ---------------------------------------------------------------------
# ✅ User-Based Recommendations
# ---------------------------------------------------------------------
def get_user_based_recommendations(customer_id, top_n=5):
    """
    Combo of:  
    - User purchase history  
    - Similar customers  
    """

    return get_purchase_history_signal(customer_id, top_n=top_n)


# ---------------------------------------------------------------------
# ✅ Purchase History Signals — MOST IMPORTANT
# ---------------------------------------------------------------------
def get_purchase_history_signal(customer_id, top_n=5):
    """
    Uses real customer purchase history to recommend products.
    - Finds products purchased by similar customers.
    """

    # 1. Get all products purchased by the user
    user_products = PurchaseHistory.objects.filter(
        customer_id=customer_id
    ).values_list("product_id", flat=True)

    if not user_products:
        return []

    # 2. Users who bought same products
    similar_customers = PurchaseHistory.objects.filter(
        product_id__in=user_products
    ).exclude(customer_id=customer_id).values_list("customer_id", flat=True)

    if not similar_customers:
        return []

    # 3. Products they purchased
    qs = (
        PurchaseHistory.objects.filter(customer_id__in=similar_customers)
        .exclude(product_id__in=user_products)
        .values("product_id", "product__product_name")
        .annotate(freq=Count("product_id"))
        .order_by("-freq")[:top_n]
    )

    return [
        {"product_id": row["product_id"], "product_name": row["product__product_name"], "score": row["freq"]}
        for row in qs
    ]

 

# ------------------------
# Train and save collaborative (item-item) model
# ------------------------
def train_and_save_model():
    """
    Train item-item similarity (cosine) from Rating table and save with SavedModel.
    """
    try:
        qs = Rating.objects.all().values("customer_id", "product_id", "rating")
        df = pd.DataFrame(list(qs))

        if df.empty:
            print("❌ No ratings found in DB.")
            return None

        matrix = df.pivot_table(index="customer_id", columns="product_id", values="rating", aggfunc="mean").fillna(0)

        sim = cosine_similarity(matrix.T)
        sim_df = pd.DataFrame(sim, index=matrix.columns, columns=matrix.columns)

        model_path = os.path.join(TRAINED_MODELS_DIR, "recommender_similarity.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(sim_df, f)

        SavedModel.objects.update_or_create(
            name="recommender_similarity",
            defaults={"file_path": model_path},
        )

        print(f"✅ Model trained (items={len(sim_df)}) and saved → {model_path}")
        return sim_df
    except Exception as e:
        print("Train model error:", e)
        return None


def recommendations_with_scores(user_id, top_n=5):
    """Return top-N recommendations with predicted scores."""
    from recommender.models import Rating, Item
    import pandas as pd

    # Get recommended items
    items = generate_recommendations_for_user(user_id, top_n=top_n)

    # Load collaborative similarity matrix
    similarity_matrix = load_trained_model()
    if similarity_matrix is None:
        return [
            {"product_id": r.product_id, "title": r.title, "category": r.category, "score": None}
            for r in items
        ]

    # Create user-item pivot table
    ratings_df = pd.DataFrame(list(Rating.objects.all().values("customer_id", "product_id", "rating")))
    if ratings_df.empty:
        return [
            {"product_id": r.product_id, "title": r.title, "category": r.category, "score": None}
            for r in items
        ]

    pivot_table = ratings_df.pivot_table(index="customer_id", columns="product_id", values="rating").fillna(0)

    if user_id not in pivot_table.index:
        return [
            {"product_id": r.product_id, "title": r.title, "category": r.category, "score": None}
            for r in items
        ]

    user_vector = pivot_table.loc[user_id].values.reshape(1, -1)
    scores = (similarity_matrix.values @ user_vector.T).flatten()

    scored_items = []
    for r in items:
        if r.product_id in pivot_table.columns:
            score = scores[pivot_table.columns.get_loc(r.product_id)]
        else:
            score = None
        scored_items.append({
            "product_id": r.product_id,
            "title": r.title,
            "category": r.category,
            "score": float(score) if score is not None else None
        })

    return scored_items


from recommender.models import Item, Rating
from crmapp.models import customer_details

def recommender_for_customer(customer_id, top_n=5):
    """
    Simple example: returns top N items for a given customer.
    Replace this with your real recommendation logic.
    """
    # Placeholder: top-rated items (just as example)
    top_items = Item.objects.all()[:top_n]
    return top_items



# ------------------------------------------------------------
# 3. COMBINED FUNCTION (Upsell + Cross-sell)
# ------------------------------------------------------------
def get_upsell_crosssell(product_id):
    return {
        "upsell": get_upsell_recommendations(product_id),
        "cross_sell": get_crosssell_recommendations(product_id)
    }


# recommender_engine.py

import pickle
import numpy as np

MODEL_FILE = "recommender/trained_models/simple_cf_model.pkl"

# Load model only once
with open(MODEL_FILE, "rb") as f:
    cf_model = pickle.load(f)



def recommend_products(customer_id, num_recs=5):
    """
    Unified function used by Django views.
    """
    try:
        if customer_id not in cf_model:
            return []

        user_scores = cf_model[customer_id]

        sorted_scores = sorted(
            user_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {"product_id": pid, "score": float(score)}
            for pid, score in sorted_scores[:num_recs]
        ]

    except Exception as e:
        print("Recommendation Engine Error:", e)
        return []


import numpy as np
import pickle
import os
from django.conf import settings

# --------------------------------------------------------
# LOAD HYBRID MODEL
# -------------------------------------------------------- 
# --------------------------------------------------------
# LOAD HYBRID MODEL (CF-based)
# --------------------------------------------------------
HYBRID_MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "recommender",
    "trained_models",
    "hybrid_recommender.pkl"
)
# HYBRID MODEL
try:
    print(f"📥 Loading Hybrid Recommendation Model: {HYBRID_MODEL_PATH}")

    with open(HYBRID_MODEL_PATH, "rb") as f:
        HYBRID_MODEL = pickle.load(f)

    print("✅ Hybrid Recommender Loaded Successfully")

except Exception as e:
    print(f"❌ Hybrid Model Load Error: {e}")
    HYBRID_MODEL = None


# --------------------------------------------------------
# HYBRID RECOMMENDATION FUNCTION
# -------------------------------------------------------- 
def get_hybrid_recommendations(customer_id, top_n=10):
    """
    Hybrid = CF Only (because no content model exists)
    """

    if HYBRID_MODEL is None:
        return {"error": "Hybrid model not loaded"}

    cf = HYBRID_MODEL["cf"]
    user_item = cf["user_item_matrix"]
    sim_matrix = cf["similarity_df"]

    # 1. User must exist
    if customer_id not in user_item.index:
        return []  # New user → no recommendations yet

    # 2. Get similarity scores
    sim_scores = sim_matrix.loc[customer_id]

    # 3. Sort similar users
    similar_users = sim_scores.sort_values(ascending=False)[1:11]

    # 4. Weighted score of products
    weighted_scores = user_item.loc[similar_users.index].T.dot(similar_users)

    # 5. Remove products the user already bought
    purchased = user_item.loc[customer_id]
    weighted_scores = weighted_scores[purchased == 0]

    # 6. Top-N products
    top_products = weighted_scores.sort_values(ascending=False).head(top_n)

    return [
        {"product_id": int(pid), "score": float(score)}
        for pid, score in top_products.items()
    ]


import pickle
import numpy as np
import pandas as pd
import os

MODEL_DIR = os.path.join("recommender", "trained_models")

# ------------------------------------------------------------
# LOAD HYBRID MODEL
# ------------------------------------------------------------
def load_hybrid():
    path = os.path.join(MODEL_DIR, "hybrid_recommender.pkl")

    with open(path, "rb") as f:
        model = pickle.load(f)

    return model


# ------------------------------------------------------------
# GET RECOMMENDATIONS FOR A CUSTOMER
# ------------------------------------------------------------
def get_recommendations(customer_id, top_n=5):
    model = load_hybrid()

    cf_model = model["cf"]
    user_item = cf_model["user_item_matrix"]
    similarity_df = cf_model["similarity_df"]

    # --------------------------------------------------------
    # Step 1 — Check if user exists
    # --------------------------------------------------------
    if customer_id not in similarity_df.index:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found in training data.",
            "recommendations": []
        }

    # --------------------------------------------------------
    # Step 2 — Get similar customers
    # --------------------------------------------------------
    similarity_scores = similarity_df.loc[customer_id]

    # Remove self
    similarity_scores = similarity_scores.drop(customer_id)

    similar_customers = similarity_scores.sort_values(ascending=False)

    # --------------------------------------------------------
    # Step 3 — Score products based on similar customers
    # --------------------------------------------------------
    weighted_scores = {}

    for other_user, score in similar_customers.items():
        user_products = user_item.loc[other_user]

        for product_id, rating in user_products.items():
            if rating > 0:  # means user purchased
                if product_id not in weighted_scores:
                    weighted_scores[product_id] = 0
                weighted_scores[product_id] += score * rating

    # --------------------------------------------------------
    # Step 4 — Remove products already purchased by target user
    # --------------------------------------------------------
    target_products = user_item.loc[customer_id]
    purchased_products = set(target_products[target_products > 0].index)

    # Filter only new products
    recommendations = {
        product: score
        for product, score in weighted_scores.items()
        if product not in purchased_products
    }

    # --------------------------------------------------------
    # Step 5 — Sort & return top-N
    # --------------------------------------------------------
    sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)

    result = [int(prod_id) for prod_id, _ in sorted_recs[:top_n]]

    return {
        "status": "success",
        "customer_id": customer_id,
        "recommended_products": result
    }


# recommender/recommender_engine.py

import pickle
import numpy as np

# ------------ CF MODEL LOADING ---------------
CF_MODEL_PATH = r"C:\Users\mansi\Downloads\PartA_02-12-25Teim\recommender\trained_models\recommender_model.pkl"

try:
    with open(CF_MODEL_PATH, "rb") as f:
        cf_model = pickle.load(f)
    print("✅ CF Model Loaded in recommender_engine.py")
except Exception as e:
    print("❌ CF Model Load Failed:", e)
    cf_model = None


# ------------ HYBRID MODEL LOADING -------------
HYBRID_MODEL_PATH = r"C:\Users\mansi\Downloads\PartA_02-12-25Teim\recommender\trained_models\hybrid_recommender.pkl"

try:
    with open(HYBRID_MODEL_PATH, "rb") as f:
        hybrid_model = pickle.load(f)
    print("✅ Hybrid Model Loaded in recommender_engine.py")
except Exception as e:
    print("❌ Hybrid Model Load Failed:", e)
    hybrid_model = None



# ============================================================
# 1️⃣  CF RECOMMENDER FUNCTION
# ============================================================

def get_cf_recommendations(customer_id, top_k=10):
    """Return CF-based recommendations."""
    
    if cf_model is None:
        return []

    try:
        recommendations = cf_model.get_recommendations(customer_id, top_k)
        return recommendations
    except Exception as e:
        print("❌ CF Recommender Error:", e)
        return []


# ============================================================
# 2️⃣  HYBRID RECOMMENDER FUNCTION
# ============================================================

def get_hybrid_recommendations(customer_id, top_k=10):
    """Return hybrid recommendations."""
    
    if hybrid_model is None:
        return []

    try:
        recommendations = hybrid_model.predict(customer_id, top_k)
        return recommendations
    except Exception as e:
        print("❌ Hybrid Recommender Error:", e)
        return []



from crmapp.models import customer_details, Product
from recommender.models import PestRecommendation
from django.utils import timezone

def generate_demographic_recommendations():
    customers = customer_details.objects.all()
    products = Product.objects.all()

    count = 0

    for customer in customers:

        city = (customer.soldtopartycity or "").lower()
        ctype = (customer.customer_type or "").lower()

        # RULE 1 — City-based (Mosquito hotspots)
        if city in ["mumbai", "thane", "navi mumbai", "pune", "nagpur"]:
            for p in products:
                if "Mosquito" in p.product_name:
                    PestRecommendation.objects.create(
                        customer_id=customer.id,
                        recommended_product=p,
                        recommendation_type="demographic",
                        confidence_score=0.83,
                        created_at=timezone.now(),
                    )
                    count += 1

        # RULE 2 — Commercial & Industrial
        if ctype in ["commercial", "warehouse", "industrial"]:
            for p in products:
                if p.category == "Fumigation":
                    PestRecommendation.objects.create(
                        customer_id=customer.id,
                        recommended_product=p,
                        recommendation_type="demographic",
                        confidence_score=0.78,
                        created_at=timezone.now(),
                    )
                    count += 1

        # RULE 3 — Residential
        if ctype in ["residential", "home", "flat", "apartment"]:
            for p in products:
                if (
                    "Cockroach" in p.product_name
                    or "Ant" in p.product_name
                    or "General pest" in p.product_name
                ):
                    PestRecommendation.objects.create(
                        customer_id=customer.id,
                        recommended_product=p,
                        recommendation_type="demographic",
                        confidence_score=0.72,
                        created_at=timezone.now(),
                    )
                    count += 1

    return count

from .hybrid_service import get_hybrid_recommendations
from .demographic_service import (
    get_demographic_recommendations,
    save_demographic_recommendations
)
from .models import PestRecommendation


def generate_full_recommendations(customer_id, top_n=10):
    """
    Full unified pipeline:
    1. Try Hybrid
    2. Fallback → Demographic
    3. Save to DB
    4. Return structured JSON
    """
    # Step 1 — Try hybrid
    hybrid_results = get_hybrid_recommendations(customer_id, top_n)

    if hybrid_results and len(hybrid_results) > 0:
        method_used = "hybrid"
        final_results = hybrid_results
    else:
        method_used = "demographic"
        demo = get_demographic_recommendations(customer_id, limit=top_n)
        final_results = demo["recommended_products"]

    # Step 2 — Clear old rows
    PestRecommendation.objects.filter(
        customer_id=str(customer_id)
    ).delete()

    # Step 3 — Save new results
    if final_results:
        formatted = []
        for rec in final_results:
            formatted.append({
                "product_id": rec["product_id"],
                "score": rec["score"]
            })

        save_demographic_recommendations(customer_id, formatted)

    # Step 4 — Final JSON response
    return {
        "status": "success",
        "customer_id": customer_id,
        "method_used": method_used,
        "total_recommendations": len(final_results),
        "results": final_results
    }

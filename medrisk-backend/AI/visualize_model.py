import joblib
import json
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.tree import plot_tree
import pandas as pd
import numpy as np

# Set up the Streamlit page
st.set_page_config(page_title="MedRisk AI - Model Visualizer", layout="wide")
st.title("MedRisk AI: Decision Tree Visualizer")
st.markdown("This dashboard visualizes the 'dummy model' (`disease_model.pkl`) trained on the synthetic dataset. It shows how the model uses blood parameters to predict a disease.")

# Load model and config
# @st.cache_resource is a decorator that tells Streamlit to load this only once
@st.cache_resource
def load_model():
    """
    Loads the trained model and its configuration file.
    """
    try:
        model = joblib.load("disease_model.pkl")
        with open("model_config.json") as f:
            config = json.load(f)
        return model, config
    except FileNotFoundError:
        st.error("FATAL ERROR: Could not find 'disease_model.pkl' or 'model_config.json'.")
        st.error("Please run `python train_model.py` in your terminal first!")
        return None, None

model_pipeline, config = load_model()

# If the model failed to load, stop the script
if model_pipeline is None:
    st.stop()

# Get features and classes from the loaded config
features = config["features"]
classes = config["classes"]
tree = model_pipeline.named_steps['classifier'] # Extract the tree from the pipeline

# --- Sidebar ---
st.sidebar.header("Model Information")
st.sidebar.write(f"**Algorithm:** `DecisionTreeClassifier`")
st.sidebar.write(f"**Trained Features:**")
st.sidebar.json(features)
st.sidebar.write(f"**Prediction Classes:**")
st.sidebar.json(classes)
st.sidebar.write(f"**Total Nodes:** {tree.tree_.node_count}")

# =======================================
# 1. Interactive Decision Tree Plot
# =======================================
st.subheader("1. Interactive Decision Tree")
st.markdown("This shows the 'if-then' logic of the model. You can adjust the depth to see more detail.")

# Add a slider to control the depth
max_depth = st.slider("Select Tree Depth to Display", min_value=1, max_value=10, value=3)

# Create the plot
fig, ax = plt.subplots(figsize=(25, 12)) # Make it wide
plot_tree(
    tree,
    feature_names=features,
    class_names=classes,
    filled=True,
    rounded=True,
    fontsize=10,
    max_depth=max_depth, # Use the slider value
    ax=ax
)
ax.set_title(f"Decision Tree (Showing Depth ≤ {max_depth})", fontsize=20)
st.pyplot(fig)



# =======================================
# 2. Feature Importance Bar Chart
# =======================================
st.subheader("2. Feature Importance")
st.markdown("This chart shows which blood markers the model found *most* important for making a prediction. A higher score is more important.")

importances = tree.feature_importances_
indices = np.argsort(importances)[::-1]
sorted_features = [features[i] for i in indices]

fig_imp, ax_imp = plt.subplots(figsize=(10, 6))
bars = ax_imp.bar(range(len(features)), importances[indices], color='skyblue', edgecolor='black')
ax_imp.set_xticks(range(len(features)))
ax_imp.set_xticklabels(sorted_features, rotation=45)
ax_imp.set_ylabel("Importance Score")
ax_imp.set_title("Which Blood Marker Matters Most?")

# Add labels on top of bars
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax_imp.text(bar.get_x() + bar.get_width()/2, height + 0.01,
              f'{importances[indices[i]]:.3f}', ha='center', va='bottom', fontsize=10)
st.pyplot(fig_imp)

# =======================================
# 3. Sample Prediction Path
# =======================================
st.subheader("3. Interactive Prediction Simulator")
st.markdown("Enter different blood values below to see what the model will predict and *why*.")

cols = st.columns(len(features))
user_input = {}

# Get the median values from the imputer to use as defaults
default_values = model_pipeline.named_steps['imputer'].statistics_

for i, feat in enumerate(features):
    with cols[i]:
        # Use the median as the default value in the input box
        val = st.number_input(f"{feat}", value=float(default_values[i]), format="%.2f")
        user_input[feat] = val

if st.button("Predict Disease"):
    # Create a DataFrame from the user's input
    X_input = pd.DataFrame([user_input], columns=features)
    
    # Get prediction and probabilities
    pred_id = model_pipeline.predict(X_input)[0]
    pred_class = classes[pred_id]
    probas = model_pipeline.predict_proba(X_input)[0]
    
    st.success(f"**Predicted Disease: {pred_class}** (Confidence: {probas[pred_id]:.1%})")
    
    st.write("**Confidence Scores for all classes:**")
    st.dataframe(pd.DataFrame([probas], columns=classes).style.format("{:.1%}"))

    # Show decision path
    st.write("**Decision Path (How the AI decided):**")
    node_indicator = tree.decision_path(X_input)
    leaf_id = tree.apply(X_input)[0]
    path_indices = node_indicator.indices
    
    for node_id in path_indices:
        if leaf_id == node_id:
            # This is the final leaf node
            st.write(f"→ **Leaf Node {node_id}** → **Final Prediction: {pred_class}**")
        else:
            # This is a decision (split) node
            
            # --- THIS IS THE FIX ---
            # We must use tree.tree_ (with underscore) to access internal attributes
            feature_index = tree.tree_.feature[node_id]
            threshold = tree.tree_.threshold[node_id]
            # -----------------------

            feature_name = features[feature_index]
            value = X_input.iloc[0, feature_index]
            
            # Check if the imputer was used
            imputed_value = model_pipeline.named_steps['imputer'].transform(X_input)[0][feature_index]
            imputed_text = f" (value was {imputed_value:.2f})" if value != imputed_value else ""
            
            condition = "≤" if value <= threshold else ">"
            st.write(f"**Node {node_id}:** Is **{feature_name}** ({value:.2f}{imputed_text}) **{condition} {threshold:.2f}**? **Yes.**")
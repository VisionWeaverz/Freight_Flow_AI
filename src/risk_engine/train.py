"""Training script for scikit-learn disruption risk model on synthetic data."""

def train_risk_model(data_path: str = "data/synthetic/training_signals.csv"):
    """Trains scikit-learn classifier/regressor and exports model weights."""
    print(f"Training risk model on {data_path}...")
    # TODO: Load dataset, train-test split, evaluate accuracy, and pickle model
    pass

if __name__ == "__main__":
    train_risk_model()

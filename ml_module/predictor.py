# File: ml_module/predictor.py

import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import os
import warnings
warnings.filterwarnings('ignore')

class ProtocolPredictor:
    """ML-based protocol predictor for MANET scenarios"""
    
    def __init__(self, model_path=None):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = ['NumNodes', 'NodeSpeed', 'AreaSize', 'TrafficLoad', 'TxRange']
        
        if model_path and os.path.exists(model_path):
            try:
                self.load_model(model_path)
            except:
                print("Could not load existing model, will create new one if needed")
                self.create_default_model()
        else:
            self.create_default_model()
    
    def create_default_model(self):
        """Create a basic model with synthetic training data"""
        print("Creating default ML model for protocol prediction...")
        
        # Generate synthetic training data based on protocol characteristics
        np.random.seed(42)
        n_samples = 1000
        
        # Features: NumNodes, NodeSpeed, AreaSize, TrafficLoad, TxRange
        X = []
        y = []
        
        for _ in range(n_samples):
            num_nodes = np.random.randint(20, 100)
            node_speed = np.random.uniform(1, 30)
            area_size = np.random.randint(500, 2000)
            traffic_load = np.random.randint(1, 50)
            tx_range = np.random.randint(50, 300)
            
            # Rule-based protocol selection for training data
            protocol = self._rule_based_selection(num_nodes, node_speed, area_size, traffic_load, tx_range)
            
            X.append([num_nodes, node_speed, area_size, traffic_load, tx_range])
            y.append(protocol)
        
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        # Train model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        
        # Evaluate
        accuracy = self.model.score(X_test, y_test)
        print(f"Default model trained with accuracy: {accuracy:.3f}")
    
    def _rule_based_selection(self, num_nodes, node_speed, area_size, traffic_load, tx_range):
        """Rule-based protocol selection for generating training data"""
        
        # Network density
        network_density = (num_nodes * np.pi * (tx_range/1000)**2) / (area_size/1000000)
        
        # Mobility factor
        mobility_factor = node_speed / 30.0
        
        # Traffic factor
        traffic_factor = traffic_load / 50.0
        
        # AODV: Good for moderate mobility and traffic
        aodv_score = (1 - mobility_factor) * 0.4 + (1 - traffic_factor) * 0.3 + min(network_density, 1.0) * 0.3
        
        # DSDV: Good for low mobility, high density
        dsdv_score = (1 - mobility_factor) * 0.6 + min(network_density, 1.0) * 0.4
        
        # DSR: Good for low traffic, small networks
        dsr_score = (1 - traffic_factor) * 0.5 + (1 - num_nodes/100.0) * 0.5
        
        # OLSR: Good for dense, high traffic networks
        olsr_score = min(network_density, 1.0) * 0.5 + traffic_factor * 0.5
        
        scores = {'AODV': aodv_score, 'DSDV': dsdv_score, 'DSR': dsr_score, 'OLSR': olsr_score}
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def predict(self, features_dict):
        """Predict best protocol for given network parameters"""
        if self.model is None:
            return "AODV", 0.5  # Default fallback
        
        try:
            # Extract features in correct order
            feature_vector = [features_dict[name] for name in self.feature_names]
            feature_vector = np.array(feature_vector).reshape(1, -1)
            
            # Scale features
            feature_vector_scaled = self.scaler.transform(feature_vector)
            
            # Predict
            prediction = self.model.predict(feature_vector_scaled)[0]
            probabilities = self.model.predict_proba(feature_vector_scaled)[0]
            confidence = max(probabilities)
            
            return prediction, confidence
            
        except Exception as e:
            print(f"Prediction error: {e}")
            return "AODV", 0.5
    
    def save_model(self, path):
        """Save the trained model"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"Model saved to {path}")
    
    def load_model(self, path):
        """Load a trained model"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        print(f"Model loaded from {path}")
    
    def update_model_from_results(self, test_results):
        """Update model based on actual test results (online learning simulation)"""
        if not test_results or self.model is None:
            return
        
        try:
            # Extract features and best protocols from test results
            X_new = []
            y_new = []
            
            # Group results by scenario and find best protocol for each
            scenarios = {}
            for result in test_results:
                scenario_id = result.get('scenario_id') or result.get('scenario')
                if scenario_id not in scenarios:
                    scenarios[scenario_id] = []
                scenarios[scenario_id].append(result)
            
            for scenario_id, results in scenarios.items():
                # Find best protocol for this scenario
                best_result = max(results, key=lambda x: x.get('score', 0))
                best_protocol = best_result.get('protocol')
                
                # Extract scenario parameters (would need to be passed from test results)
                # For now, use dummy values - in real implementation, store scenario params
                feature_vector = [50, 10, 1000, 15, 150]  # dummy values
                
                X_new.append(feature_vector)
                y_new.append(best_protocol)
            
            if X_new:
                X_new = np.array(X_new)
                y_new = np.array(y_new)
                
                # Scale new features
                X_new_scaled = self.scaler.transform(X_new)
                
                # Retrain model with new data (in practice, you'd combine with old data)
                self.model.fit(X_new_scaled, y_new)
                print(f"Model updated with {len(X_new)} new examples")
                
        except Exception as e:
            print(f"Error updating model: {e}")


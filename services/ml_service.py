import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import json
import os
from collections import defaultdict
import logging

from models.acat import ACATRecord, ACATStatus, ContraFirm
from services.learning_service import ContraFirmLearningService

logger = logging.getLogger(__name__)

class ACATMLService:
    """Machine Learning service for ACAT success prediction and contra firm analysis."""
    
    def __init__(self, learning_service: ContraFirmLearningService):
        self.learning_service = learning_service
        self.models = {}
        self.feature_encoders = {}
        self.scalers = {}
        self.model_version = "1.0"
        self.model_path = "models/ml_models"
        
        # Ensure model directory exists
        os.makedirs(self.model_path, exist_ok=True)
        
        # Initialize models
        self._initialize_models()
        
        # Load existing models if available
        self._load_models()
    
    def _initialize_models(self):
        """Initialize ML models for different prediction tasks."""
        self.models = {
            'success_prediction': RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            ),
            'status_prediction': GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            ),
            'rejection_risk': RandomForestClassifier(
                n_estimators=50,
                max_depth=8,
                random_state=42,
                class_weight='balanced'
            )
        }
    
    def _load_models(self):
        """Load pre-trained models from disk."""
        try:
            for model_name in self.models.keys():
                model_file = os.path.join(self.model_path, f"{model_name}_v{self.model_version}.joblib")
                if os.path.exists(model_file):
                    self.models[model_name] = joblib.load(model_file)
                    logger.info(f"Loaded {model_name} model from {model_file}")
        except Exception as e:
            logger.warning(f"Could not load existing models: {e}")
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            for model_name, model in self.models.items():
                model_file = os.path.join(self.model_path, f"{model_name}_v{self.model_version}.joblib")
                joblib.dump(model, model_file)
                logger.info(f"Saved {model_name} model to {model_file}")
        except Exception as e:
            logger.error(f"Could not save models: {e}")
    
    def prepare_training_data(self, acat_records: List[ACATRecord]) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
        """Prepare training data from ACAT records."""
        if not acat_records:
            return pd.DataFrame(), {}
        
        # Convert ACAT records to DataFrame
        data = []
        for record in acat_records:
            # Calculate days since submission
            days_since_submission = (datetime.utcnow() - record.submitted_at).days if record.submitted_at else 0
            
            # Extract features
            features = {
                'contra_firm': record.contra_firm,
                'delivering_account': record.delivering_account,
                'receiving_account': record.receiving_account,
                'account_type': record.account_type,
                'days_since_submission': days_since_submission,
                'submission_month': record.submitted_at.month if record.submitted_at else 0,
                'submission_day_of_week': record.submitted_at.weekday() if record.submitted_at else 0,
                'account_length_delivering': len(record.delivering_account),
                'account_length_receiving': len(record.receiving_account),
                'is_weekend_submission': 1 if record.submitted_at and record.submitted_at.weekday() >= 5 else 0,
                'is_month_end': 1 if record.submitted_at and record.submitted_at.day >= 25 else 0,
                'has_special_chars_delivering': 1 if any(c in record.delivering_account for c in '!@#$%^&*()') else 0,
                'has_special_chars_receiving': 1 if any(c in record.receiving_account for c in '!@#$%^&*()') else 0,
                'account_similarity': self._calculate_account_similarity(record.delivering_account, record.receiving_account),
                'contra_firm_success_rate': self.learning_service.get_firm_success_rate(record.contra_firm),
                'current_status': record.status.value,
                'is_successful': 1 if record.status in [ACATStatus.COMPLETED, ACATStatus.APPROVED] else 0,
                'is_rejected': 1 if record.status in [ACATStatus.REJECTED, ACATStatus.FAILED] else 0,
                'is_pending': 1 if record.status in [ACATStatus.PENDING, ACATStatus.IN_REVIEW] else 0
            }
            data.append(features)
        
        df = pd.DataFrame(data)
        
        # Prepare target variables
        targets = {
            'success': df['is_successful'].values,
            'status': df['current_status'].values,
            'rejection': df['is_rejected'].values
        }
        
        return df, targets
    
    def _calculate_account_similarity(self, account1: str, account2: str) -> float:
        """Calculate similarity between two account numbers."""
        if not account1 or not account2:
            return 0.0
        
        # Simple character-based similarity
        common_chars = set(account1.lower()) & set(account2.lower())
        total_chars = set(account1.lower()) | set(account2.lower())
        
        if not total_chars:
            return 0.0
        
        return len(common_chars) / len(total_chars)
    
    def train_models(self, acat_records: List[ACATRecord]) -> Dict[str, Dict]:
        """Train all ML models with ACAT data."""
        if len(acat_records) < 10:
            return {"error": "Insufficient data for training. Need at least 10 records."}
        
        logger.info(f"Training models with {len(acat_records)} ACAT records")
        
        # Prepare training data
        df, targets = self.prepare_training_data(acat_records)
        
        # Feature engineering
        feature_df = self._engineer_features(df)
        
        # Prepare features and targets
        X = feature_df.drop(['current_status', 'is_successful', 'is_rejected', 'is_pending'], axis=1, errors='ignore')
        
        results = {}
        
        # Train success prediction model
        if len(targets['success']) > 0 and len(set(targets['success'])) > 1:
            X_success = X.copy()
            y_success = targets['success']
            
            # Encode categorical features
            X_success_encoded = self._encode_features(X_success, 'success')
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_success_encoded, y_success, test_size=0.2, random_state=42, stratify=y_success
            )
            
            # Train model
            self.models['success_prediction'].fit(X_train, y_train)
            
            # Evaluate
            y_pred = self.models['success_prediction'].predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            results['success_prediction'] = {
                'accuracy': accuracy,
                'training_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_importance': self._get_feature_importance(X_success.columns, self.models['success_prediction'])
            }
        
        # Train rejection risk model
        if len(targets['rejection']) > 0 and len(set(targets['rejection'])) > 1:
            X_rejection = X.copy()
            y_rejection = targets['rejection']
            
            # Encode categorical features
            X_rejection_encoded = self._encode_features(X_rejection, 'rejection')
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_rejection_encoded, y_rejection, test_size=0.2, random_state=42, stratify=y_rejection
            )
            
            # Train model
            self.models['rejection_risk'].fit(X_train, y_train)
            
            # Evaluate
            y_pred = self.models['rejection_risk'].predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            results['rejection_risk'] = {
                'accuracy': accuracy,
                'training_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_importance': self._get_feature_importance(X_rejection.columns, self.models['rejection_risk'])
            }
        
        # Save trained models
        self._save_models()
        
        results['training_summary'] = {
            'total_records': len(acat_records),
            'features_used': len(X.columns),
            'models_trained': len([k for k in results.keys() if k != 'training_summary']),
            'training_date': datetime.utcnow().isoformat()
        }
        
        return results
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer additional features for ML models."""
        df = df.copy()
        
        # Create contra firm features
        df['contra_firm_length'] = df['contra_firm'].str.len()
        df['contra_firm_word_count'] = df['contra_firm'].str.split().str.len()
        
        # Create account features
        df['total_account_length'] = df['account_length_delivering'] + df['account_length_receiving']
        df['account_length_diff'] = abs(df['account_length_delivering'] - df['account_length_receiving'])
        
        # Create temporal features
        df['is_quarter_end'] = df['submission_month'].isin([3, 6, 9, 12])
        df['is_year_end'] = df['submission_month'] == 12
        
        # Create interaction features
        df['contra_firm_success_rate_normalized'] = df['contra_firm_success_rate'] * 100
        
        return df
    
    def _encode_features(self, X: pd.DataFrame, model_name: str) -> np.ndarray:
        """Encode categorical features for ML models."""
        X_encoded = X.copy()
        
        # Encode categorical columns
        categorical_columns = ['contra_firm', 'delivering_account', 'receiving_account', 'account_type']
        
        for col in categorical_columns:
            if col in X_encoded.columns:
                if col not in self.feature_encoders:
                    self.feature_encoders[col] = LabelEncoder()
                    X_encoded[col] = self.feature_encoders[col].fit_transform(X_encoded[col].astype(str))
                else:
                    # Handle unseen categories
                    unique_values = X_encoded[col].astype(str).unique()
                    known_values = self.feature_encoders[col].classes_
                    unseen_values = set(unique_values) - set(known_values)
                    
                    if unseen_values:
                        # Add unseen values to encoder
                        all_values = list(known_values) + list(unseen_values)
                        self.feature_encoders[col] = LabelEncoder()
                        self.feature_encoders[col].fit(all_values)
                    
                    X_encoded[col] = self.feature_encoders[col].transform(X_encoded[col].astype(str))
        
        # Scale numerical features
        numerical_columns = X_encoded.select_dtypes(include=[np.number]).columns
        if len(numerical_columns) > 0:
            if model_name not in self.scalers:
                self.scalers[model_name] = StandardScaler()
                X_encoded[numerical_columns] = self.scalers[model_name].fit_transform(X_encoded[numerical_columns])
            else:
                X_encoded[numerical_columns] = self.scalers[model_name].transform(X_encoded[numerical_columns])
        
        return X_encoded.values
    
    def _get_feature_importance(self, feature_names: List[str], model) -> List[Dict]:
        """Get feature importance from trained model."""
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            feature_importance = list(zip(feature_names, importances))
            feature_importance.sort(key=lambda x: x[1], reverse=True)
            return [{'feature': name, 'importance': float(imp)} for name, imp in feature_importance[:10]]
        return []
    
    def predict_acat_success(self, acat_record: ACATRecord) -> Dict[str, Any]:
        """Predict success probability for an ACAT record."""
        if 'success_prediction' not in self.models:
            return {"error": "Success prediction model not trained"}
        
        # Prepare features for prediction
        df, _ = self.prepare_training_data([acat_record])
        feature_df = self._engineer_features(df)
        X = feature_df.drop(['current_status', 'is_successful', 'is_rejected', 'is_pending'], axis=1, errors='ignore')
        
        # Encode features
        X_encoded = self._encode_features(X, 'success')
        
        # Make prediction
        success_prob = self.models['success_prediction'].predict_proba(X_encoded)[0]
        
        return {
            'success_probability': float(success_prob[1]),  # Probability of success
            'failure_probability': float(success_prob[0]),  # Probability of failure
            'prediction_confidence': float(max(success_prob)),
            'model_version': self.model_version,
            'prediction_date': datetime.utcnow().isoformat()
        }
    
    def predict_rejection_risk(self, acat_record: ACATRecord) -> Dict[str, Any]:
        """Predict rejection risk for an ACAT record."""
        if 'rejection_risk' not in self.models:
            return {"error": "Rejection risk model not trained"}
        
        # Prepare features for prediction
        df, _ = self.prepare_training_data([acat_record])
        feature_df = self._engineer_features(df)
        X = feature_df.drop(['current_status', 'is_successful', 'is_rejected', 'is_pending'], axis=1, errors='ignore')
        
        # Encode features
        X_encoded = self._encode_features(X, 'rejection')
        
        # Make prediction
        rejection_prob = self.models['rejection_risk'].predict_proba(X_encoded)[0]
        
        return {
            'rejection_probability': float(rejection_prob[1]),  # Probability of rejection
            'acceptance_probability': float(rejection_prob[0]),  # Probability of acceptance
            'risk_level': self._get_risk_level(rejection_prob[1]),
            'model_version': self.model_version,
            'prediction_date': datetime.utcnow().isoformat()
        }
    
    def _get_risk_level(self, rejection_prob: float) -> str:
        """Convert rejection probability to risk level."""
        if rejection_prob >= 0.7:
            return "HIGH"
        elif rejection_prob >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_contra_firm_insights(self, contra_firm: str) -> Dict[str, Any]:
        """Get ML-powered insights for a specific contra firm."""
        firm_preferences = self.learning_service.get_firm_preferences(contra_firm)
        common_issues = self.learning_service.get_common_issues_for_firm(contra_firm)
        
        # Analyze patterns using ML insights
        insights = {
            'firm_name': contra_firm,
            'success_rate': firm_preferences.get('success_rate', 0.0),
            'total_submissions': firm_preferences.get('total_submissions', 0),
            'common_issues': common_issues,
            'risk_factors': self._analyze_risk_factors(contra_firm, firm_preferences),
            'recommendations': self._generate_recommendations(contra_firm, firm_preferences),
            'last_updated': firm_preferences.get('last_updated'),
            'ml_analysis': {
                'firm_classification': self._classify_firm_behavior(contra_firm, firm_preferences),
                'trend_analysis': self._analyze_trends(contra_firm, firm_preferences),
                'optimization_suggestions': self._suggest_optimizations(contra_firm, firm_preferences)
            }
        }
        
        return insights
    
    def _analyze_risk_factors(self, contra_firm: str, firm_preferences: Dict) -> List[str]:
        """Analyze risk factors for a contra firm."""
        risk_factors = []
        
        success_rate = firm_preferences.get('success_rate', 0.0)
        total_submissions = firm_preferences.get('total_submissions', 0)
        
        if success_rate < 0.3:
            risk_factors.append("Very low success rate - high rejection risk")
        elif success_rate < 0.5:
            risk_factors.append("Below average success rate")
        
        if total_submissions < 5:
            risk_factors.append("Limited historical data - predictions less reliable")
        
        # Analyze common rejection patterns
        common_rejections = firm_preferences.get('common_rejections', {})
        if common_rejections:
            top_rejection = max(common_rejections.items(), key=lambda x: x[1])
            risk_factors.append(f"Frequent rejections in: {top_rejection[0]}")
        
        return risk_factors
    
    def _generate_recommendations(self, contra_firm: str, firm_preferences: Dict) -> List[str]:
        """Generate recommendations for improving ACAT success with a contra firm."""
        recommendations = []
        
        success_rate = firm_preferences.get('success_rate', 0.0)
        
        if success_rate < 0.5:
            recommendations.append("Consider pre-validation before submission")
            recommendations.append("Review common rejection patterns and address proactively")
        
        common_rejections = firm_preferences.get('common_rejections', {})
        if common_rejections:
            recommendations.append(f"Focus on improving: {', '.join(list(common_rejections.keys())[:3])}")
        
        recommendations.append("Monitor submission timing - avoid peak rejection periods")
        recommendations.append("Implement automated validation checks")
        
        return recommendations
    
    def _classify_firm_behavior(self, contra_firm: str, firm_preferences: Dict) -> str:
        """Classify contra firm behavior pattern."""
        success_rate = firm_preferences.get('success_rate', 0.0)
        total_submissions = firm_preferences.get('total_submissions', 0)
        
        if total_submissions < 3:
            return "INSUFFICIENT_DATA"
        elif success_rate >= 0.8:
            return "ACCOMMODATING"
        elif success_rate >= 0.6:
            return "STANDARD"
        elif success_rate >= 0.4:
            return "STRICT"
        else:
            return "VERY_STRICT"
    
    def _analyze_trends(self, contra_firm: str, firm_preferences: Dict) -> Dict[str, Any]:
        """Analyze trends in contra firm behavior."""
        # This would analyze temporal patterns if we had time-series data
        return {
            'trend_direction': 'STABLE',  # Would be calculated from historical data
            'seasonal_patterns': 'NONE_DETECTED',
            'volatility': 'LOW'
        }
    
    def _suggest_optimizations(self, contra_firm: str, firm_preferences: Dict) -> List[str]:
        """Suggest optimizations for working with a contra firm."""
        suggestions = []
        
        success_rate = firm_preferences.get('success_rate', 0.0)
        
        if success_rate < 0.6:
            suggestions.append("Implement stricter pre-submission validation")
            suggestions.append("Consider alternative submission timing")
            suggestions.append("Review and improve data quality standards")
        
        suggestions.append("Automate common validation checks")
        suggestions.append("Implement real-time feedback system")
        
        return suggestions
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Get performance metrics for all trained models."""
        performance = {
            'model_version': self.model_version,
            'models_available': list(self.models.keys()),
            'last_training_date': None,  # Would be stored in metadata
            'model_status': {}
        }
        
        for model_name in self.models.keys():
            performance['model_status'][model_name] = {
                'trained': True,
                'ready_for_prediction': True,
                'feature_count': len(self.feature_encoders) if self.feature_encoders else 0
            }
        
        return performance




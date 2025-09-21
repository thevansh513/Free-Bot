import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

class UserDataStorage:
    def __init__(self, filename: str = "user_data.json"):
        self.filename = filename
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from JSON file, create if doesn't exist"""
        if not os.path.exists(self.filename):
            initial_data = {
                "users": {},
                "referrals": {},
                "orders": []
            }
            self._save_data(initial_data)
            return initial_data
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"users": {}, "referrals": {}, "orders": []}
    
    def _save_data(self, data: Optional[Dict[str, Any]] = None):
        """Save data to JSON file"""
        if data is None:
            data = self.data
        
        with open(self.filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
    
    def create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> bool:
        """Create a new user if doesn't exist"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data["users"]:
            # Generate unique referral code
            referral_code = str(uuid.uuid4())[:8]
            while any(user.get("referral_code") == referral_code for user in self.data["users"].values()):
                referral_code = str(uuid.uuid4())[:8]
            
            self.data["users"][user_id_str] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "balance": 0,  # Balance in views
                "ads_watched": 0,
                "referral_code": referral_code,
                "referred_by": None,
                "referrals_count": 0,
                "join_date": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
            self._save_data()
            return True
        
        return False
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data by ID"""
        return self.data["users"].get(str(user_id))
    
    def update_user_activity(self, user_id: int):
        """Update user's last activity timestamp"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["last_activity"] = datetime.now().isoformat()
            self._save_data()
    
    def add_balance(self, user_id: int, amount: int) -> bool:
        """Add balance to user (amount in views)"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["balance"] += amount
            self._save_data()
            return True
        return False
    
    def subtract_balance(self, user_id: int, amount: int) -> bool:
        """Subtract balance from user if sufficient"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            if self.data["users"][user_id_str]["balance"] >= amount:
                self.data["users"][user_id_str]["balance"] -= amount
                self._save_data()
                return True
        return False
    
    def add_ad_view(self, user_id: int) -> int:
        """Add ad view and return total views (every 10 views = reward)"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["ads_watched"] += 1
            ads_watched = self.data["users"][user_id_str]["ads_watched"]
            
            # Every 10 ad views = 1 view reward
            if ads_watched % 10 == 0:
                self.add_balance(user_id, 1)
            
            self._save_data()
            return ads_watched
        return 0
    
    def get_referral_link(self, user_id: int, bot_username: str) -> str:
        """Get user's referral link"""
        user = self.get_user(user_id)
        if user:
            referral_code = user["referral_code"]
            return f"https://t.me/{bot_username}?start={referral_code}"
        return ""
    
    def process_referral(self, user_id: int, referral_code: str) -> bool:
        """Process referral when new user joins with code"""
        user_id_str = str(user_id)
        
        # Find referrer by referral code
        referrer_id = None
        for uid, user_data in self.data["users"].items():
            if user_data.get("referral_code") == referral_code:
                referrer_id = uid
                break
        
        if referrer_id and referrer_id != user_id_str:
            # Set referral relationship
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["referred_by"] = int(referrer_id)
                
                # Give referrer +100 views reward
                self.data["users"][referrer_id]["balance"] += 100
                self.data["users"][referrer_id]["referrals_count"] += 1
                
                # Track referral in separate section
                if referrer_id not in self.data["referrals"]:
                    self.data["referrals"][referrer_id] = []
                
                self.data["referrals"][referrer_id].append({
                    "user_id": user_id,
                    "date": datetime.now().isoformat(),
                    "reward": 100
                })
                
                self._save_data()
                return True
        
        return False
    
    def create_order(self, user_id: int, video_link: str, quantity: int, total_cost: int) -> str:
        """Create a new order"""
        order_id = str(uuid.uuid4())[:12]
        
        order = {
            "order_id": order_id,
            "user_id": user_id,
            "video_link": video_link,
            "quantity": quantity,
            "total_cost": total_cost,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        self.data["orders"].append(order)
        self._save_data()
        return order_id
    
    def get_user_orders(self, user_id: int) -> list:
        """Get all orders for a user"""
        return [order for order in self.data["orders"] if order["user_id"] == user_id]
    
    def get_all_users(self) -> Dict[str, Any]:
        """Get all users (for admin broadcast)"""
        return self.data["users"]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get general statistics"""
        total_users = len(self.data["users"])
        total_orders = len(self.data["orders"])
        total_referrals = sum(len(refs) for refs in self.data["referrals"].values())
        
        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_referrals": total_referrals,
            "active_users_today": 0  # Can be enhanced later
        }
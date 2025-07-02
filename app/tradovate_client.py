import requests
import json
from datetime import datetime, timedelta
from dateutil import parser
import time

class TradovateClient:
    def __init__(self, access_token=None, refresh_token=None):
        self.base_url = "https://live.tradovate.com/v1"
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session = requests.Session()
        
    def authenticate(self, username, password):
        """Authenticate with Tradovate API using username/password"""
        auth_url = f"{self.base_url}/auth/access_token"
        auth_data = {
            "name": username,
            "password": password,
            "appId": "Sample App",
            "appVersion": "1.0",
            "deviceId": "web",
            "cid": "Sample App"
        }
        
        try:
            response = self.session.post(auth_url, json=auth_data)
            response.raise_for_status()
            auth_response = response.json()
            
            self.access_token = auth_response.get('accessToken')
            self.refresh_token = auth_response.get('refreshToken')
            
            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': auth_response.get('expiresIn')
            }
        except requests.exceptions.RequestException as e:
            raise Exception(f"Authentication failed: {str(e)}")
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            raise Exception("No refresh token available")
            
        refresh_url = f"{self.base_url}/auth/refresh_token"
        refresh_data = {
            "refreshToken": self.refresh_token,
            "cid": "Sample App"
        }
        
        try:
            response = self.session.post(refresh_url, json=refresh_data)
            response.raise_for_status()
            refresh_response = response.json()
            
            self.access_token = refresh_response.get('accessToken')
            self.refresh_token = refresh_response.get('refreshToken')
            
            return {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_in': refresh_response.get('expiresIn')
            }
        except requests.exceptions.RequestException as e:
            raise Exception(f"Token refresh failed: {str(e)}")
    
    def _get_headers(self):
        """Get headers with authentication token"""
        if not self.access_token:
            raise Exception("No access token available")
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_accounts(self):
        """Get user accounts"""
        accounts_url = f"{self.base_url}/account/list"
        
        try:
            response = self.session.get(accounts_url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get accounts: {str(e)}")
    
    def get_trades(self, account_id, start_date=None, end_date=None, limit=1000):
        """Get trades for a specific account"""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
            
        # Convert dates to ISO format
        start_iso = start_date.isoformat() + 'Z'
        end_iso = end_date.isoformat() + 'Z'
        
        trades_url = f"{self.base_url}/trade/list"
        params = {
            'accountId': account_id,
            'startTime': start_iso,
            'endTime': end_iso,
            'limit': limit
        }
        
        try:
            response = self.session.get(trades_url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get trades: {str(e)}")
    
    def get_positions(self, account_id):
        """Get current positions for an account"""
        positions_url = f"{self.base_url}/position/list"
        params = {'accountId': account_id}
        
        try:
            response = self.session.get(positions_url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get positions: {str(e)}")
    
    def get_products(self):
        """Get available products/symbols"""
        products_url = f"{self.base_url}/product/list"
        
        try:
            response = self.session.get(products_url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get products: {str(e)}")
    
    def parse_trade_data(self, tradovate_trade):
        """Parse Tradovate trade data into our format"""
        try:
            # Extract basic trade information
            ticker = tradovate_trade.get('symbol', '')
            side = tradovate_trade.get('side', '').upper()
            direction = 'Long' if side == 'BUY' else 'Short'
            
            # Parse dates
            exec_time = tradovate_trade.get('execTime')
            if exec_time:
                exec_date = parser.parse(exec_time)
            else:
                exec_date = datetime.now()
            
            # Extract prices and quantities
            price = float(tradovate_trade.get('price', 0))
            quantity = float(tradovate_trade.get('quantity', 0))
            
            # Calculate PnL if available
            pnl = tradovate_trade.get('realizedPnL')
            if pnl is not None:
                pnl = float(pnl)
            
            return {
                'ticker': ticker,
                'direction': direction,
                'entry_date': exec_date,
                'entry_price': price,
                'position_size': quantity,
                'pnl': pnl,
                'tradovate_id': tradovate_trade.get('id'),
                'notes': f"Imported from Tradovate - Order ID: {tradovate_trade.get('orderId', 'N/A')}"
            }
        except Exception as e:
            raise Exception(f"Failed to parse trade data: {str(e)}")
    
    def get_trades_for_import(self, account_id, start_date=None, end_date=None):
        """Get trades formatted for import into our system"""
        trades = self.get_trades(account_id, start_date, end_date)
        
        if not trades:
            return []
        
        parsed_trades = []
        for trade in trades:
            try:
                parsed_trade = self.parse_trade_data(trade)
                parsed_trades.append(parsed_trade)
            except Exception as e:
                # Log error but continue with other trades
                print(f"Error parsing trade {trade.get('id')}: {str(e)}")
                continue
        
        return parsed_trades 
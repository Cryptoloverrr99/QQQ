import logging
import os
from telegram import Bot
from apscheduler.schedulers.blocking import BlockingScheduler
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TokenAnalyzer:
    def __init__(self):
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.channel = os.getenv('TELEGRAM_CHANNEL')
        self.already_alerted = set()
    
    def fetch_token_data(self):
        try:
            response = requests.get(
                "https://api.dexscreener.com/token-profiles/latest/v1",
                timeout=20,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            return response.json().get('tokenProfiles', []) if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"API Error: {str(e)}")
            return []

    def check_conditions(self, token):
        try:
            # Extraction des données avec gestion des valeurs manquantes
            supply = token.get('totalSupply', float('inf'))
            market_cap = token.get('marketCap', 0)
            liquidity = token.get('liquidity', {}).get('usd', 0)
            locked = token.get('lockedLiquidityPercentage')
            burned = token.get('burnedLiquidityPercentage')
            
            # Vérification de la liquidité lock/burn
            liquidity_check = True
            if locked is not None and burned is not None:
                liquidity_check = (locked + burned) >= 99
            elif locked is not None:
                liquidity_check = locked >= 99
            elif burned is not None:
                liquidity_check = burned >= 99

            conditions = [
                supply <= 1e9,
                market_cap >= 50000,
                liquidity >= 20000,
                liquidity_check,
                self.check_top_holders(token.get('holders', [])),
                token.get('makersCount', 0) >= 50,
                token.get('holdersCount', 0) >= 20,
                token.get('volume24h', 0) >= 10000,
                token.get('pairCreatedAt') is not None,
                self.check_socials(token.get('socials', {}))
            ]
            
            return all(conditions)
            
        except Exception as e:
            logger.error(f"Check error: {str(e)}")
            return False

def run_check(self):
    try:
        for token in self.fetch_token_data():
            if token['address'] not in self.already_alerted:
                if self.check_conditions(token):
                    # Envoi effectif du message
                    self.bot.send_message(
                        chat_id=self.channel,  # ID du channel depuis .env
                        text=self.format_alert(token),  # Message formaté
                        parse_mode="Markdown",  # Activation du Markdown
                        disable_web_page_preview=True  # Désactive les prévisualisations
                    )
                    self.already_alerted.add(token['address'])
    except Exception as e:
        logger.error(f"Erreur d'envoi : {str(e)}")
    
    def check_top_holders(self, holders):
        try:
            top_10 = sum(sorted(
                [h['percentage'] for h in holders], 
                reverse=True
            )[:10])
            return top_10 <= 40
        except:
            return False

    def check_socials(self, socials):
        return bool(socials.get('twitter')) and bool(socials.get('website'))

    def format_alert(self, token):
        socials = token.get('socials', {})
        return (
            "🚨 **ALERTE MEMECOIN** 🚨\n\n"
            f"• Token : {token.get('symbol')}\n"
            f"• Market Cap : ${token.get('marketCap', 0):,.0f}\n"
            f"• Liquidité : ${token.get('liquidity', {}).get('usd', 0):,.0f}\n"
            f"• Volume 24h : ${token.get('volume24h', 0):,.0f}\n"
            f"• Holders : {token.get('holdersCount', 0)}\n"
            f"• Boosté : {'✅' if token.get('isBoosted') else '❌'}\n\n"
            f"[Chart]({token.get('url')}) | "
            f"[Twitter]({socials.get('twitter', '')}) | "
            f"[Site]({socials.get('website', '')})"
        )

    def run_check(self):
        try:
            for token in self.fetch_token_data():
                if token['address'] not in self.already_alerted:
                    if self.check_conditions(token):
                        self.bot.send_message(
                            chat_id=self.channel,
                            text=self.format_alert(token),
                            parse_mode="Markdown"
                        )
                        self.already_alerted.add(token['address'])
        except Exception as e:
            logger.error(f"Runtime error: {str(e)}")

if __name__ == '__main__':
    analyzer = TokenAnalyzer()
    scheduler = BlockingScheduler()
    scheduler.add_job(analyzer.run_check, 'interval', seconds=180)
    scheduler.start()

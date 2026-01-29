import stripe
import os
from flask import Flask, redirect, jsonify
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()
stripe.api_key = "你的_SECRET_KEY"

app = Flask(__name__)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        # 建立結帳會話
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price_data': {
                    'currency': 'twd',
                    'product_data': {'name': '網站會員服務'},
                    'unit_amount': 50000, # NT$500 (金額以分計)
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://your-website.com',
            cancel_url='https://your-website.com',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(port=4242)

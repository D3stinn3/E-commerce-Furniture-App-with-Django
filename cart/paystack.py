"""Thin wrapper around the Paystack Standard (redirect) transaction API.

Credentials are read from settings (which read them from the .env file):
    PAYSTACK_SECRET_KEY, PAYSTACK_PUBLIC_KEY, PAYSTACK_CURRENCY

Docs: https://paystack.com/docs/api/transaction/
"""
import requests
from django.conf import settings

PAYSTACK_BASE_URL = 'https://api.paystack.co'


def _headers():
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def initialize_transaction(email, amount_subunit, reference, callback_url):
    """Create a transaction and return the hosted-page URL to redirect the buyer to.

    `amount_subunit` must already be in the smallest currency unit
    (e.g. KES cents = price * 100).

    Returns a dict: {'authorization_url': str, 'reference': str} on success,
    or raises requests.HTTPError / ValueError on failure.
    """
    payload = {
        'email': email,
        'amount': int(amount_subunit),
        'currency': settings.PAYSTACK_CURRENCY,
        'reference': reference,
        'callback_url': callback_url,
    }
    response = requests.post(
        f'{PAYSTACK_BASE_URL}/transaction/initialize',
        json=payload,
        headers=_headers(),
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get('status'):
        raise ValueError(data.get('message', 'Paystack initialization failed'))
    return data['data']


def verify_transaction(reference):
    """Verify a transaction by reference.

    Returns the Paystack `data` dict (which includes 'status': 'success'|... and
    'amount'). Raises on transport errors.
    """
    response = requests.get(
        f'{PAYSTACK_BASE_URL}/transaction/verify/{reference}',
        headers=_headers(),
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get('status'):
        raise ValueError(data.get('message', 'Paystack verification failed'))
    return data['data']

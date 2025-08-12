# controllers/google_verification.py
from odoo import http
from odoo.http import request

class GoogleVerificationController(http.Controller):
    @http.route('/googlec0d10d6b063a8f8b.html', auth='public', type='http')
    def google_verification(self):
        return request.make_response(
            "google-site-verification: googlec0d10d6b063a8f8b.html",
            headers=[('Content-Type', 'text/html')]
        )

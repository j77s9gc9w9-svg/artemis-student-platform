# Security Testing and Hardening

Implemented:
- Input validation for email, password, title, description, and capacity.
- Password strength rules.
- JWT authorization on protected routes.
- RBAC for admin-only routes.
- Ownership checks for deleting events.
- Parameterized SQL queries to prevent SQL injection.
- HTML escaping and CSP headers to reduce XSS risk.
- Request body size limit.
- Secure session cookie settings.

Manual tests:
1. Try weak passwords.
2. Try registering with role=admin.
3. Try protected endpoints without JWT.
4. Try SQL injection payloads in login fields.
5. Try XSS payloads in event title.
6. Try deleting another user’s event.
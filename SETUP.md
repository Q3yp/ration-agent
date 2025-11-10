# Authentication System Setup Guide

This guide covers setting up the new user authentication system for the Ration Agent application.

## Prerequisites

1. **Database Setup**
   - Ensure PostgreSQL is running with pgvector extension
   - Database should be accessible at `localhost:5433`

2. **Environment Configuration**
   - Copy `.env.example` to `.env`
   - Set your `JWT_SECRET` to a secure random string (at least 32 characters)
   - Ensure `DATABASE_URL` points to your PostgreSQL instance
   - For Google login, set `GOOGLE_OAUTH_CLIENT_ID` (backend) and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (frontend) so the web client can render the Google Sign-In button

## Setup Steps

### 1. Install Backend Dependencies

```bash
cd backend
uv sync
```

### 2. Run Database Migration

This creates the users table and adds a default admin user:

```bash
cd backend
uv run python migrations/add_users_table.py
```

**Default Admin Credentials:**
- Email: `admin@example.com`
- Username: `admin`
- Password: `admin123`

**⚠️ Important:** Change the admin password immediately after first login!

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 4. Start the Services

**Terminal 1 - Backend:**
```bash
cd backend
uv run python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### 5. Configure Google OAuth (optional)

1. Create OAuth 2.0 credentials in the Google Cloud Console (Web application).
2. Add the authorized JavaScript origin `http://localhost:3000` for local development.
3. Update your environment files:
   - In `backend/.env`, set `GOOGLE_OAUTH_CLIENT_ID`.
   - In `frontend/.env`, set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` to the same value so the web client can initialize the Google Sign-In button.
4. Re-run `uv sync` in `backend/` so the new Google verification dependencies are installed.
5. Until valid credentials are provided, the backend will return HTTP 503 from `/auth/google/id-token` to signal that Google Sign-In is disabled.

## Testing the Authentication System

1. **Access the Application**
   - Open http://localhost:3000
   - You should be redirected to the login screen

2. **Login as Admin**
   - Use the default admin credentials above
   - You should be redirected to the main chat interface

3. **Test Admin Panel**
   - Click the "用户管理" (User Management) button in the top-right corner
   - You should see the user management interface in Chinese
   - Try creating a new user account

4. **Test User Management**
   - Create a new user with different permissions
   - Log out and log in as the new user
   - Verify the user only sees their own sessions

## API Endpoints

The authentication system adds these new endpoints:

### Authentication Routes
- `POST /auth/jwt/login` - Login with email/password
- `POST /auth/jwt/logout` - Logout (invalidate token)
- `POST /auth/register` - Register new user (can be disabled)
- `GET /auth/users/me` - Get current user info
- `POST /auth/google/id-token` - Exchange a Google ID token (generated client-side) for a session JWT

### Admin Routes (Superuser only)
- `GET /admin/users` - List all users
- `POST /admin/users` - Create new user
- `GET /admin/users/{user_id}` - Get user details
- `PUT /admin/users/{user_id}` - Update user
- `DELETE /admin/users/{user_id}` - Delete user

### Protected Existing Routes
All existing routes now require authentication:
- Session management (`/sessions/*`)
- Chat streaming (`/chat/*`)
- File operations (`/files/*`)

## Database Schema Changes

### New Tables
- `users` - User accounts with FastAPI-Users fields
- Indexes on email, username, and active status

### Modified Tables
- `sessions` - Added `user_id` foreign key to associate sessions with users

## Security Features

1. **JWT Token Authentication**
   - 1-hour token lifetime
   - Secure token generation with configurable secret

2. **Password Security**
   - Bcrypt hashing for all passwords
   - Password validation and strength requirements

3. **Role-Based Access Control**
   - Regular users: Access to own sessions only
   - Admins (superusers): Access to user management

4. **Session Isolation**
   - Users can only see and interact with their own chat sessions
   - Admin can manage all users but sessions remain isolated

## Troubleshooting

### Backend Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running on port 5433
   - Check DATABASE_URL in .env file

2. **Migration Fails**
   - Ensure database exists and is accessible
   - Check for any existing conflicting table structures

3. **JWT Token Issues**
   - Verify JWT_SECRET is set in .env
   - Clear browser localStorage if experiencing auth issues

### Frontend Issues

1. **Login Page Not Showing**
   - Check browser console for errors
   - Verify API proxy configuration in next.config.js

2. **Authentication Headers Missing**
   - Check browser localStorage for 'auth_token'
   - Verify authHeaders utility is being used in API calls

3. **Admin Panel Access Denied**
   - Ensure user has is_superuser=true in database
   - Check user role assignment in admin panel

## Production Considerations

1. **Change Default Credentials**
   - Immediately change the default admin password
   - Consider disabling the registration endpoint

2. **Environment Variables**
   - Use a strong, unique JWT_SECRET (32+ characters)
   - Set appropriate token lifetime for your use case

3. **Database Security**
   - Use strong database credentials
   - Enable SSL for database connections

4. **CORS Configuration**
   - Update CORS origins for production domains
   - Remove localhost origins in production

## Next Steps

After setting up authentication, you can:

1. **Customize User Roles**
   - Extend the User model with additional role fields
   - Implement more granular permissions

2. **Add Email Verification**
   - Configure SMTP settings
   - Enable email verification workflow

3. **Social Login**
   - Configure Google OAuth2 by creating credentials in the Google Cloud Console
   - Optional: extend with additional providers (GitHub, WeChat, etc.) following the same pattern

4. **Password Reset**
   - Implement forgot password functionality
   - Add password reset email templates

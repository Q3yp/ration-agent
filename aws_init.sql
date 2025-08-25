-- Database initialization script for AWS RDS PostgreSQL
-- Run this script on your AWS RDS instance to create required tables and extensions

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(1024) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'user'
);

-- Create indexes for users table (better performance)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Create user_sessions table for session management
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_path TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for user_sessions table
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active_deleted ON user_sessions(active, deleted);
CREATE INDEX IF NOT EXISTS idx_user_sessions_last_accessed ON user_sessions(last_accessed);

-- Insert default admin user (password: admin123)
-- Note: Change this password immediately after first login!
INSERT INTO users (
    id,
    email,
    username,
    hashed_password,
    is_active,
    is_superuser,
    is_verified,
    role,
    full_name
) VALUES (
    gen_random_uuid(),
    'admin@example.com',
    'admin',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', -- hashed "admin123"
    TRUE,
    TRUE,
    TRUE,
    'admin',
    'Administrator'
) ON CONFLICT (email) DO NOTHING;

-- LangGraph checkpoint tables will be auto-created by the application
-- You can pre-create them here if needed for specific database policies

COMMENT ON TABLE users IS 'User authentication and profile data';
COMMENT ON TABLE user_sessions IS 'User session management for dairy nutrition agent';
COMMENT ON EXTENSION vector IS 'Required for pgvector operations in LangGraph';
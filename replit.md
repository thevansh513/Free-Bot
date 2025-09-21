# Overview

This is a Telegram bot application designed for a social media marketing service that allows users to watch ads, earn money through referrals, and purchase views for their content. The bot provides a complete user management system with balance tracking, referral programs, and order processing capabilities. Users can interact with the bot through a menu-driven interface to access various features like watching ads for rewards, referring friends, buying views for their videos, checking their balance, and contacting administrators.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Technology**: Python Telegram Bot library (python-telegram-bot==22.4)
- **Architecture Pattern**: Event-driven command and message handling
- **State Management**: In-memory user state tracking for conversation flows
- **Interface**: Custom reply keyboard with menu options for user navigation

## Data Storage
- **Storage Solution**: File-based JSON storage system
- **Data Structure**: Three main collections - users, referrals, and orders
- **User Management**: Comprehensive user profiles with balance tracking, referral codes, and activity monitoring
- **Persistence**: Automatic data saving to user_data.json file with UTF-8 encoding

## User Flow Management
- **Conversation States**: State machine pattern for handling multi-step interactions
- **Rate Limiting**: In-memory tracking for ad viewing frequency
- **Authentication**: Admin-level permissions for broadcast and management features

## External API Integration
- **Order Processing**: RESTful API integration for purchasing views
- **Ad System**: Third-party advertising script integration for monetization
- **Error Handling**: Comprehensive exception handling for external service failures

## Web Interface
- **Framework**: Flask web server for health checks and status monitoring
- **Endpoints**: JSON API responses for system status verification

# External Dependencies

## Core Dependencies
- **Flask 3.1.2**: Web framework for HTTP endpoints and health monitoring
- **requests 2.32.5**: HTTP client library for external API communications
- **python-telegram-bot 22.4**: Official Telegram Bot API wrapper for bot functionality

## Environment Configuration
- **BOT_TOKEN**: Telegram Bot API authentication token (required)
- **ADMIN_ID**: Administrator user ID for privileged operations (default: 7981712298)

## Third-Party Services
- **Order API**: External service at testuser2.onrender.com for view purchasing functionality
- **Advertisement Network**: Integration with libtl.com SDK for ad serving and revenue generation
- **Telegram API**: Real-time messaging and user interaction platform

## Data Storage
- **File System**: JSON-based persistent storage for user data, referrals, and order history
- **UUID Generation**: Built-in Python library for unique referral code generation